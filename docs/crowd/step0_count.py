"""Step 0 count: wallets and trades in Polymarket daily NVDA and SPX up/down markets, last 60 days."""
import json, time, urllib.request, collections, datetime as dt, sys
UA = {"User-Agent": "forecast-duel-step0"}
def get(url):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(2 * (k + 1))
    return {"_error": str(err)}
end = dt.date(2026, 10, 20); out = {}
for fam in ("nvda", "spx"):
    wallets = collections.Counter(); days = collections.defaultdict(set); markets = []; d = end
    while d > end - dt.timedelta(days=60):
        if d.weekday() < 5:
            slug = f"{fam}-up-or-down-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
            ev = get(f"https://gamma-api.polymarket.com/events?slug={slug}")
            if isinstance(ev, list) and ev:
                for m in ev[0]["markets"]:
                    cid = m["conditionId"]; seen = set(); off = 0; capped = False
                    while True:
                        t = get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}")
                        if not isinstance(t, list): capped = t.get("_error", "err"); break
                        if not t: break
                        for x in t:
                            key = (x.get("transactionHash"), x["proxyWallet"], x["asset"], x["size"], x["price"], x["timestamp"])
                            if key not in seen:
                                seen.add(key); wallets[x["proxyWallet"]] += 1; days[x["proxyWallet"]].add(slug)
                        if len(t) < 500: break
                        off += 500; time.sleep(0.06)
                    markets.append({"slug": slug, "volume": float(m.get("volume") or 0), "trades": len(seen), "capped": capped})
            else:
                markets.append({"slug": slug, "missing": True})
        d -= dt.timedelta(days=1)
    top = wallets.most_common(10)
    out[fam] = {"markets_found": sum(1 for m in markets if not m.get("missing")),
                "markets_missing": sum(1 for m in markets if m.get("missing")),
                "trades": sum(m.get("trades", 0) for m in markets),
                "volume_usd": round(sum(m.get("volume", 0) for m in markets)),
                "wallets": len(wallets),
                "wallets_30plus": sum(1 for v in wallets.values() if v >= 30),
                "top10": top,
                "top10_days": [len(days[w]) for w, _ in top],
                "wallets_30plus_and_10days": sum(1 for w, v in wallets.items() if v >= 30 and len(days[w]) >= 10),
                "wallets_20days": sum(1 for w in days if len(days[w]) >= 20), "capped_markets": [m["slug"] for m in markets if m.get("capped")],
                "markets": markets}
    print(fam, {k: v for k, v in out[fam].items() if k not in ("markets",)}, file=sys.stderr, flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
