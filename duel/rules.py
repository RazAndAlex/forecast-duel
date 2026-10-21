"""Replay docs/crowd/rules.json (one habit per wallet) on NVDA closes."""
from __future__ import annotations

import json
import operator
from pathlib import Path

from .score import luck_p

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "docs" / "crowd" / "rules.json"
OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}


def load(path=RULES) -> list[dict]:
    p = Path(path)
    return json.loads(p.read_text())["rules"] if p.exists() else []


def _split(n: int, hits: int) -> dict:
    return {"n": n, "hits": hits, "direction_hit_pct": round(100 * hits / n, 2) if n else None}


def replay(rule: dict, closes: dict[str, float], crowd_rows: list[dict]) -> dict:
    """Score one rule. Days before the first crowd day are out_of_sample, crowd days in_sample.
    A rule that reads up_price only exists on crowd days."""
    up_price = {r["date"]: r["up_price"] for r in crowd_rows}
    first = min(up_price) if up_price else None
    dates = sorted(closes)
    tally = {"in_sample": [0, 0], "out_of_sample": [0, 0]}
    for i in range(2, len(dates)):
        d = dates[i]
        move = closes[d] - closes[dates[i - 1]]
        if move == 0:
            continue
        feats = {"prior_day_return": closes[dates[i - 1]] / closes[dates[i - 2]] - 1}
        if d in up_price:
            feats["up_price"] = up_price[d]
        if any(c["feature"] not in feats for c in rule["if"]):
            continue
        if d in up_price:
            side = "in_sample"
        elif first and d < first:
            side = "out_of_sample"
        else:
            continue
        ok = all(OPS[c["op"]](feats[c["feature"]], c["value"]) for c in rule["if"])
        pick = rule["then"] if ok else rule.get("else")
        if pick is None:
            continue
        tally[side][0] += 1
        tally[side][1] += (pick == "up") == (move > 0)
    n = sum(t[0] for t in tally.values())
    hits = sum(t[1] for t in tally.values())
    return {"id": rule["id"], "wallet": rule["wallet"], "text": rule["text"], **_split(n, hits),
            "p": luck_p(n, hits), "in_sample": _split(*tally["in_sample"]),
            "out_of_sample": _split(*tally["out_of_sample"])}


def score_all(closes: dict[str, float], crowd_rows: list[dict], path=RULES) -> list[dict]:
    return [replay(r, closes, crowd_rows) for r in load(path)]
