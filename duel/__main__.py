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
from .assets import ASSETS, MODELS, Asset
from .calendar import target_dates
from .models import KronosModel, TimestralModel


def run(backfill: int) -> None:
    t0 = time.time()
    prices = {a.ticker: fetch.fetch(a) for a in ASSETS}

    # (made_on, ticker, kind, live): the newest bar live, the N before it as warm-up.
    jobs: list[tuple[str, Asset, bool]] = []
    for asset in ASSETS:
        dates = [d.strftime("%Y-%m-%d") for d in prices[asset.ticker].index]
        jobs.append((dates[-1], asset, True))
        if backfill:
            jobs += [(d, asset, False) for d in dates[-backfill - 1 : -1]]

    existing = store.keys(store.load())
    pending = {m: [j for j in jobs if (j[0], j[1].ticker, m) not in existing] for m in MODELS}
    new_rows: list[dict] = []

    # Naive first: no model in memory.
    for made_on, asset, live in pending["naive"]:
        ticker = asset.ticker
        last = float(prices[ticker].loc[:made_on]["close"].iloc[-1])
        new_rows.append(store.record(made_on, ticker, "naive", [last] * 5, None, None,
                                     target_dates(made_on, asset), live))

    def model_phase(name, make_forecast):
        todo = pending[name]
        if not todo:
            return
        model = make_forecast()
        try:
            for i, (made_on, asset, live) in enumerate(todo, 1):
                ticker = asset.ticker
                try:
                    values, q10, q90 = run_one(model, name, prices, made_on, asset)
                    new_rows.append(store.record(made_on, ticker, name, values, q10, q90,
                                                 target_dates(made_on, asset), live))
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


def run_one(model, name, prices, made_on, asset):
    ticker = asset.ticker
    dates = target_dates(made_on, asset)
    if name == "kronos":
        # 150 bars: longer windows make Kronos drift 10-30% on daily data (see docs/build-report.md).
        df = prices[ticker].loc[:made_on].tail(150)
        return model.forecast(df, dates), None, None
    closes = prices[ticker].loc[:made_on]["close"].tolist()[-1024:]
    return model.forecast(closes)


def smoke() -> None:
    """Load both models and forecast one asset. Writes nothing."""
    t0 = time.time()
    asset = ASSETS[0]
    ticker = asset.ticker
    prices = {ticker: fetch.fetch(asset)}
    made_on = prices[ticker].index[-1].strftime("%Y-%m-%d")
    for name, cls in (("kronos", KronosModel), ("timestral", TimestralModel)):
        pred = run_one(cls(), name, prices, made_on, asset)[0]
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
