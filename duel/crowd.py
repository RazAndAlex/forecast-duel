"""Polymarket crowd seat: the 09:30 ET Up price of the daily NVDA up/down market -> data/crowd.jsonl."""
from __future__ import annotations

import datetime as dt
import json
import time
import traceback
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendar import is_open

ROOT = Path(__file__).resolve().parent.parent
CROWD = ROOT / "data" / "crowd.jsonl"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
NY = ZoneInfo("America/New_York")


def get(url: str):
    """JSON from url, retried; on failure returns {"_error": ...}. Callers must type-check."""
    err = None
    for k in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "forecast-duel-crowd"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(k + 1)
    return {"_error": str(err)}


def slug_for(d: dt.date) -> str:
    return f"nvda-up-or-down-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"


def call(up_price: float) -> int:
    """+1 Up, -1 Down, 0 no call (exactly 0.5)."""
    return 1 if up_price > 0.5 else -1 if up_price < 0.5 else 0


def _price_before(token: str, start: int, cut: int, get) -> float | None:
    # interval=max is empty for resolved markets before ~2026-09-21, so the window comes first.
    for window in (f"startTs={start}&endTs={cut}", "interval=max"):
        r = get(f"{CLOB}/prices-history?market={token}&{window}&fidelity=60")
        hist = r.get("history") if isinstance(r, dict) else None
        if isinstance(hist, list):
            pts = [p for p in hist if p["t"] <= cut]
            if pts:
                return float(max(pts, key=lambda p: p["t"])["p"])
    return None


def market(d: dt.date, get=get) -> dict | None:
    """The gamma market object of day d (the event holds it; /markets?slug= answers empty)."""
    r = get(f"{GAMMA}/events?slug={slug_for(d)}")
    ms = r[0].get("markets") if isinstance(r, list) and r and isinstance(r[0], dict) else None
    return ms[0] if isinstance(ms, list) and ms and isinstance(ms[0], dict) else None


def fetch_day(d: dt.date, get=get) -> dict | None:
    """{date, up_price, slug} for one market day, or None when any step has no usable answer."""
    slug = slug_for(d)
    m = market(d, get)
    if m is None:
        return None
    token = json.loads(m["clobTokenIds"])[json.loads(m["outcomes"]).index("Up")]
    start = int(dt.datetime.fromisoformat(m["startDate"]).timestamp())
    cut = int(dt.datetime.combine(d, dt.time(9, 30), NY).timestamp())
    p = _price_before(token, start, cut, get)
    return None if p is None else {"date": d.isoformat(), "up_price": p, "slug": slug}


def load(path=CROWD) -> list[dict]:
    p = Path(path)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def fetch_crowd(weekdays: int = 60, today: dt.date | None = None, get=get, path=CROWD) -> int:
    """Append the missing days among the last `weekdays` weekdays; one bad day never stops the loop."""
    today = today or dt.date.today()
    known = {r["date"] for r in load(path)}
    days, d = [], today
    while len(days) < weekdays:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    now = dt.datetime.now(dt.timezone.utc)
    added = 0
    for d in sorted(days):
        if d.isoformat() in known or not is_open(d, "XNYS"):
            continue
        if dt.datetime.combine(d, dt.time(9, 30), NY) > now:
            continue
        try:
            row = fetch_day(d, get)
        except Exception:
            print(f"[crowd] {d} failed:")
            traceback.print_exc()
            continue
        if row is None:
            print(f"[crowd] {d}: no price, skipped")
            continue
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(row) + "\n")
        added += 1
    return added


def score(rows: list[dict], closes: dict[str, float]) -> dict:
    """The crowd's direction hits against the NVDA close-to-close move of each market day."""
    dates = sorted(closes)
    days, hits, n, nocall = [], 0, 0, 0
    for r in sorted(rows, key=lambda r: r["date"]):
        d = r["date"]
        if d not in closes or dates.index(d) == 0:
            continue
        move = closes[d] - closes[dates[dates.index(d) - 1]]
        c = call(r["up_price"])
        if move == 0:
            continue
        if c == 0:
            nocall += 1
            continue
        hit = (c > 0) == (move > 0)
        n += 1
        hits += hit
        days.append({"date": d, "up_price": r["up_price"], "call": "up" if c > 0 else "down",
                     "actual": "up" if move > 0 else "down", "hit": hit})
    return {"n": n, "hits": hits, "direction_hit_pct": round(100 * hits / n, 2) if n else None,
            "no_call": nocall, "days": days}
