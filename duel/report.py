"""Build site/data.json from stored forecasts plus cached or fresh prices."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from .assets import ASSETS, MODELS
from . import fetch
from .score import direction_hit, mape, next_bars
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


def _actual_after(dates: list[str], closes: list[float], made_on: str):
    """The closes of the 5 bars after made_on, or None while immature."""
    i = dates.index(made_on)
    following = closes[i + 1 : i + 6]
    return following if len(following) == 5 else None


def _metrics(rows, ticker, dates, closes, close_of, live):
    """Per-model (mapes, directions, beats) for one asset and one live split."""
    out = {}
    for model in MODELS:
        mapes, dirs, beats = [], [], []
        for r in rows:
            if r["ticker"] != ticker or r["model"] != model or r["live"] != live:
                continue
            actual = _actual_after(dates, closes, r["made_on"])
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


def build(prices: dict[str, pd.DataFrame] | None = None, out_path: Path = SITE) -> dict:
    rows = load_forecasts()
    by_key = {(r["made_on"], r["ticker"], r["model"]): r for r in rows}

    assets_out = []
    totals = {split: {m: ([], [], []) for m in MODELS} for split in ("live", "warmup")}

    for ticker, name, kind in ASSETS:
        df = prices[ticker] if prices else fetch.load_cached(ticker)
        dates = [d.strftime("%Y-%m-%d") for d in df.index]
        closes = [float(c) for c in df["close"]]
        close_of = dict(zip(dates, closes))
        last_date = dates[-1]

        asset_metrics = {split: _metrics(rows, ticker, dates, closes, close_of, live)
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
                "actual": [price(v) for v in _actual_after(dates, closes, m_on)]
                          if _actual_after(dates, closes, m_on) else None,
                "kronos": [price(v) for v in pk["values"]],
                "timestral": [price(v) for v in pt["values"]],
                "naive": [price(v) for v in pn["values"]],
            })

        assets_out.append({
            "ticker": ticker,
            "name": name,
            "kind": kind,
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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=1) + "\n")
    return data
