"""Build site/data.json from stored forecasts plus cached or fresh prices."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from .assets import ASSETS, MODELS
from . import crowd as crowd_mod, fetch, rules as rules_mod
from .calendar import target_dates
from .score import direction_hit, luck_p, mape, next_bars
from .store import load as load_forecasts

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "data.json"

MODEL_INFO = {
    "kronos": {"label": "Kronos-base", "params": "102M", "by": "Tsinghua (NeoQuasar)"},
    "timestral": {"label": "Timestral-209M", "params": "209M", "by": "Mistral AI"},
    "naive": {"label": "Naive (tomorrow = today)", "params": "0", "by": "baseline"},
}


def price(x: float) -> float:
    """2 decimals above 10, else 4 significant decimals."""
    return round(float(x), 2) if abs(x) >= 10 else float(f"{x:.4g}")


def _actual_after(close_of: dict[str, float], made_on: str, asset):
    """The closes on the 5 target dates after made_on, or None while any is missing."""
    targets = target_dates(made_on, asset)
    return [close_of[d] for d in targets] if all(d in close_of for d in targets) else None


def _metrics(rows, asset, close_of, live):
    """Per-model (mapes, directions, beats) for one asset and one live split."""
    out = {}
    ticker = asset.ticker
    for model in MODELS:
        mapes, dirs, beats = [], [], []
        for r in rows:
            if r["ticker"] != ticker or r["model"] != model or r["live"] != live:
                continue
            actual = _actual_after(close_of, r["made_on"], asset)
            if actual is None:
                continue
            lc = close_of[r["made_on"]]
            m = mape(r["values"], actual)
            mapes.append(m)
            dirs.append(direction_hit(r["values"], actual, lc))
            if model != "naive":
                n = next(
                    (x for x in rows if x["ticker"] == ticker and x["model"] == "naive"
                     and x["made_on"] == r["made_on"]),
                    None,
                )
                if n is not None:
                    beats.append(m < mape(n["values"], actual))
        out[model] = (mapes, dirs, beats)
    return out


def _stat_block(metrics, with_beats: bool) -> dict:
    block = {}
    for model in MODELS:
        mapes, dirs, beats = metrics[model]
        n = len(mapes)
        entry = {
            "n": n,
            "mape_pct": round(sum(mapes) / n, 2) if n else None,
            "direction_hit_pct": round(100 * sum(dirs) / n, 2) if n else None,
        }
        if with_beats:
            entry["beats_naive_pct"] = round(100 * sum(beats) / len(beats), 2) if beats else None
        block[model] = entry
    return block


def _crowd_keys(totals) -> dict:
    """New keys: the Polymarket crowd seat, the wallets behind it, and a luck test for every hit rate."""
    nvda = fetch.load_cached("NVDA")["close"]
    closes = {d.strftime("%Y-%m-%d"): float(c) for d, c in nvda.items()}
    rows = crowd_mod.load()
    crowd = crowd_mod.score(rows, closes)
    rules = rules_mod.score_all(closes, rows)
    wallets = ROOT / "docs" / "crowd" / "wallets" / "index.json"
    traders = {"wallets": json.loads(wallets.read_text())["kept"] if wallets.exists() else [], "rules": rules}
    luck = {"models": {split: {m: {"n": len(totals[split][m][1]), "hits": sum(totals[split][m][1]),
                                   "p": luck_p(len(totals[split][m][1]), sum(totals[split][m][1]))}
                               for m in MODELS} for split in totals},
            "crowd": {"n": crowd["n"], "hits": crowd["hits"], "p": luck_p(crowd["n"], crowd["hits"])},
            "rules": {r["id"]: {"n": r["n"], "hits": r["hits"], "p": r["p"]} for r in rules}}
    return {"crowd": crowd, "traders": traders, "luck": luck}


def build(prices: dict[str, pd.DataFrame] | None = None, out_path: Path = SITE) -> dict:
    rows = load_forecasts()
    by_key = {(r["made_on"], r["ticker"], r["model"]): r for r in rows}

    assets_out = []
    totals = {split: {m: ([], [], []) for m in MODELS} for split in ("live", "warmup")}

    for asset in ASSETS:
        ticker = asset.ticker
        df = prices[ticker] if prices else fetch.load_cached(ticker)
        dates = [d.strftime("%Y-%m-%d") for d in df.index]
        closes = [float(c) for c in df["close"]]
        close_of = dict(zip(dates, closes))
        last_date = dates[-1]

        asset_metrics = {split: _metrics(rows, asset, close_of, live)
                         for split, live in (("live", True), ("warmup", False))}
        for split, met in asset_metrics.items():
            for m in MODELS:
                a, b, c = totals[split][m]
                totals[split][m] = (a + met[m][0], b + met[m][1], c + met[m][2])

        k = by_key.get((last_date, ticker, "kronos"))
        t = by_key.get((last_date, ticker, "timestral"))
        n = by_key.get((last_date, ticker, "naive"))
        latest = None
        if n and k and t:
            latest = {
                "made_on": last_date,
                "dates": n["dates"],
                "kronos": [price(v) for v in k["values"]],
                "timestral": [price(v) for v in t["values"]],
                "timestral_q10": [price(v) for v in t["q10"]] if t.get("q10") else None,
                "timestral_q90": [price(v) for v in t["q90"]] if t.get("q90") else None,
                "naive": [price(v) for v in n["values"]],
            }

        past = []
        for m_on in sorted({m for (m, tk, _mo) in by_key if tk == ticker and m != last_date},
                           reverse=True)[:40]:
            pk, pt, pn = (by_key.get((m_on, ticker, mdl)) for mdl in MODELS)
            if not (pk and pt and pn):
                continue
            past.append({
                "made_on": m_on,
                "live": pn["live"],
                "dates": pn["dates"],
                "actual": [price(v) for v in _actual_after(close_of, m_on, asset)]
                          if _actual_after(close_of, m_on, asset) else None,
                "kronos": [price(v) for v in pk["values"]],
                "timestral": [price(v) for v in pt["values"]],
                "naive": [price(v) for v in pn["values"]],
            })

        assets_out.append({
            "ticker": ticker,
            "name": asset.name,
            "short": asset.short,
            "kind": asset.kind,
            "exchange": asset.exchange,
            "currency": asset.currency,
            "last_close": price(closes[-1]),
            "last_date": last_date,
            "history": [[d, price(c)] for d, c in zip(dates[-90:], closes[-90:])],
            "latest": latest,
            "past": past,
            "scores": {
                split: _stat_block(asset_metrics[split], with_beats=False)
                for split in ("live", "warmup")
            },
        })

    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "models": MODELS,
        "model_info": MODEL_INFO,
        "leaderboard": {
            split: _stat_block({m: totals[split][m] for m in MODELS}, with_beats=True)
            for split in ("live", "warmup")
        },
        "assets": assets_out,
    }
    data.update(_crowd_keys(totals))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=1) + "\n")
    return data
