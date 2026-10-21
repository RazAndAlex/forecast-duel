"""Who trades the daily NVDA up/down markets. Run by hand: python -m duel.traders

Writes docs/crowd/wallets/<wallet>.csv (one row per market day) and wallets/index.json.
Net Up shares: BUY Up and SELL Down count +size, SELL Up and BUY Down count -size.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import time
import traceback

from . import crowd, fetch
from .calendar import is_open

WALLETS = crowd.ROOT / "docs" / "crowd" / "wallets"
MIN_TRADES, MIN_SLUGS = 30, 10
MM_RATIO = 0.10  # market maker: |net Up shares over all days| / shares traded < 10%
DATA = "https://data-api.polymarket.com"


def market_trades(condition_id: str, get=crowd.get) -> list[dict]:
    seen, out, off = set(), [], 0
    while True:
        t = get(f"{DATA}/trades?market={condition_id}&limit=500&offset={off}")
        if not isinstance(t, list):
            break
        for x in t:
            key = (x.get("transactionHash"), x["proxyWallet"], x["asset"], x["size"], x["price"], x["timestamp"])
            if key not in seen:
                seen.add(key)
                out.append(x)
        if len(t) < 500:
            break
        off += 500
        time.sleep(0.06)
    return out


def signed(x: dict) -> float:
    s = float(x["size"]) * (1 if x["side"] == "BUY" else -1)
    return s if x["outcome"] == "Up" else -s


def run(weekdays: int = 60, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    up_price = {r["date"]: r["up_price"] for r in crowd.load()}
    closes = fetch.load_cached("NVDA")["close"]
    dates = [d.strftime("%Y-%m-%d") for d in closes.index]
    trades = collections.defaultdict(list)  # wallet -> [(date, premarket, net_up, size)]
    d = today
    for _ in range(weekdays):
        if d.weekday() < 5 and is_open(d, "XNYS"):
            iso = d.isoformat()
            try:
                m = crowd.market(d)
                if m:
                    cut = int(dt.datetime.combine(d, dt.time(9, 30), crowd.NY).timestamp())
                    for x in market_trades(m["conditionId"]):
                        trades[x["proxyWallet"]].append((iso, int(x["timestamp"]) < cut, signed(x), float(x["size"])))
            except Exception:
                print(f"[traders] {d} failed:")
                traceback.print_exc()
        d -= dt.timedelta(days=1)

    WALLETS.mkdir(parents=True, exist_ok=True)
    index, dropped = [], {"few": 0, "market_maker": 0}
    for w, ts in trades.items():
        slugs = {t[0] for t in ts}
        if len(ts) < MIN_TRADES or len(slugs) < MIN_SLUGS:
            dropped["few"] += 1
            continue
        volume = sum(t[3] for t in ts)
        net = sum(t[2] for t in ts)
        if abs(net) / volume < MM_RATIO:
            dropped["market_maker"] += 1
            continue
        per = {s: [0.0, 0.0] for s in slugs}
        for s, pre, n, _ in ts:
            per[s][1] += n
            per[s][0] += n if pre else 0
        rows, long_days = [], 0
        for s in sorted(per):
            i = dates.index(s) if s in dates else None
            if i is None or i < 2:
                continue
            move = closes.iloc[i] - closes.iloc[i - 1]
            long_days += per[s][1] > 0
            rows.append({"date": s, "net_up_premarket": round(per[s][0], 2), "net_up_day": round(per[s][1], 2),
                         "prior_day_return": round(float(closes.iloc[i - 1] / closes.iloc[i - 2] - 1), 6),
                         "up_price": up_price.get(s, ""), "actual_up": "" if move == 0 else int(move > 0)})
        with open(WALLETS / f"{w}.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
        index.append({"wallet": w, "trades": len(ts), "slugs": len(slugs), "volume_shares": round(volume),
                      "net_up_shares": round(net), "share_days_net_long_up": round(long_days / len(rows), 3)})
    index.sort(key=lambda x: -x["trades"])
    out = {"wallets_seen": len(trades), "dropped": dropped, "kept": index}
    (WALLETS / "index.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    o = run()
    print(f"seen {o['wallets_seen']}, dropped {o['dropped']}, kept {len(o['kept'])}")
