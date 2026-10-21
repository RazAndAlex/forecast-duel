# Crowd seat build report (branch crowd-traders, 2026-10-21)

Steps 0-3 and 5-9 of the plan. Step 4 (real rules) and step 10 (page) are left to the main session.

- Crowd: 58 market days scored (last 60 weekdays), 41 hits = 70.69%, 0 days at exactly 0.5. Luck test p = 0.0011.
- Wallets: 362 seen; 348 dropped for under 30 trades or under 10 slugs; 6 dropped as market makers (|net Up shares| / shares traded < 10%); 8 kept. Tables in `docs/crowd/wallets/`.
- Rules: `docs/crowd/rules.json` holds one placeholder (prior-day-return follower). It scores 299 of 630 (47.5%, p 0.91): in sample 34/58, out of sample 265/572.
- Old keys of `site/data.json` match main's, checked in `tests/test_crowd.py`. Tests: 20 passed (13 old + 7 new).

## Found on the way

- `gamma /markets?slug=` answers an empty list for these markets. `/events?slug=` returns them in `markets[0]`. `duel/crowd.py` uses the event route.
- Trader share-of-days uses days where the wallet traded; `0x61234f` is net long Up on all 39 of its days, which is a one-sided habit worth a look in step 4.
- `fetch_crowd` skips a day if the 09:30 ET cut is still in the future; a day without a price is retried next run.
- Not run: `python -m duel run` and `smoke` (they rewrite data/prices).
