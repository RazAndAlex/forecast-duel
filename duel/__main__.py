"""Entry point: python -m duel run [--backfill N]."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import resource
import sys
import time
import traceback

from . import fetch, report, store
from .assets import ASSETS, MODELS
from .models import KronosModel, TimestralModel


def target_dates(made_on: str, kind: str) -> list[str]:
    """Expected dates: next 5 weekdays for stocks, next 5 calendar days for BTC."""
    d = dt.date.fromisoformat(made_on)
    out = []
    while len(out) < 5:
        d += dt.timedelta(days=1)
        if kind == "crypto" or d.weekday() < 5:
            out.append(d.isoformat())
    return out


def run(backfill: int) -> None:
    t0 = time.time()
    prices = {t: fetch.fetch(t, kind) for t, _name, kind in ASSETS}

    # (made_on, ticker, kind, live): the newest bar live, the N before it as warm-up.
    jobs: list[tuple[str, str, str, bool]] = []
    for ticker, _name, kind in ASSETS:
        dates = [d.strftime("%Y-%m-%d") for d in prices[ticker].index]
        jobs.append((dates[-1], ticker, kind, True))
        if backfill:
            jobs += [(d, ticker, kind, False) for d in dates[-backfill - 1 : -1]]

    existing = store.keys(store.load())
    pending = {m: [j for j in jobs if (j[0], j[1], m) not in existing] for m in MODELS}
    new_rows: list[dict] = []

    # Naive first: no model in memory.
    for made_on, ticker, _kind, live in pending["naive"]:
        last = float(prices[ticker].loc[:made_on]["close"].iloc[-1])
        new_rows.append(store.record(made_on, ticker, "naive", [last] * 5, None, None,
                                     target_dates(made_on, _kind), live))

    def model_phase(name, make_forecast):
        todo = pending[name]
        if not todo:
            return
        model = make_forecast()
        try:
            for i, (made_on, ticker, kind, live) in enumerate(todo, 1):
                try:
                    values, q10, q90 = run_one(model, name, prices, made_on, ticker, kind)
                    new_rows.append(store.record(made_on, ticker, name, values, q10, q90,
                                                 target_dates(made_on, kind), live))
                except Exception:
                    print(f"[{name}] {ticker} {made_on} failed:", file=sys.stderr)
                    traceback.print_exc()
                if i % 10 == 0 or i == len(todo):
                    print(f"[{name}] {i}/{len(todo)} done", flush=True)
        finally:
            model.free()

    model_phase("kronos", KronosModel)
    model_phase("timestral", TimestralModel)

    added = store.append(new_rows)
    report.build(prices)

    wall = time.time() - t0
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)  # bytes on macOS
    store.ROOT.joinpath("data").mkdir(exist_ok=True)
    with open(store.ROOT / "data" / "runs.jsonl", "a") as f:
        f.write(json.dumps({
            "finished": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "wall_s": round(wall, 1),
            "peak_rss_mb": round(rss_mb, 1),
            "backfill": backfill,
            "new_forecasts": added,
        }) + "\n")
    print(f"run done: {added} new forecasts, wall {wall:.0f}s, peak RSS {rss_mb:.0f} MB")


def run_one(model, name, prices, made_on, ticker, kind):
    dates = target_dates(made_on, kind)
    if name == "kronos":
        # 150 bars: longer windows make Kronos drift 10-30% on daily data (see docs/build-report.md).
        df = prices[ticker].loc[:made_on].tail(150)
        return model.forecast(df, dates), None, None
    closes = prices[ticker].loc[:made_on]["close"].tolist()[-1024:]
    return model.forecast(closes)


def smoke() -> None:
    """Load both models and forecast one asset. Writes nothing."""
    t0 = time.time()
    ticker, _name, kind = ASSETS[0]
    prices = {ticker: fetch.fetch(ticker, kind)}
    made_on = prices[ticker].index[-1].strftime("%Y-%m-%d")
    for name, cls in (("kronos", KronosModel), ("timestral", TimestralModel)):
        pred = run_one(cls(), name, prices, made_on, ticker, kind)[0]
        print(f"smoke {name} {ticker} from {made_on}: {[round(float(x), 3) for x in pred]}")
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    print(f"smoke ok: wall {time.time() - t0:.0f}s, peak RSS {rss_mb:.0f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(prog="duel")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="fetch, forecast, score, write site/data.json")
    p_run.add_argument("--backfill", type=int, default=0,
                       help="also forecast the N bar dates before the latest one")
    sub.add_parser("smoke", help="load both models, forecast one asset, write nothing")
    args = parser.parse_args()
    if args.cmd == "smoke":
        smoke()
    else:
        run(args.backfill)


if __name__ == "__main__":
    main()
