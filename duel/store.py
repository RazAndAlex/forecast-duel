"""data/forecasts.jsonl: append-only store, idempotent by (made_on, ticker, model)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORECASTS = ROOT / "data" / "forecasts.jsonl"


def record(made_on, ticker, model, values, q10, q90, dates, live) -> dict:
    return {
        "made_on": made_on,
        "ticker": ticker,
        "model": model,
        "values": values,
        "q10": q10,
        "q90": q90,
        "dates": dates,
        "live": live,
    }


def load(path=FORECASTS) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def keys(rows: list[dict]) -> set[tuple]:
    return {(r["made_on"], r["ticker"], r["model"]) for r in rows}


def append(rows: list[dict], path=FORECASTS) -> int:
    """Append only the rows not stored yet; returns how many were added."""
    known = keys(load(path))
    new = [r for r in rows if (r["made_on"], r["ticker"], r["model"]) not in known]
    if new:
        with open(path, "a") as f:
            for r in new:
                f.write(json.dumps(r) + "\n")
    return len(new)
