# Asset switch to the AI set: report

Branch `assets-ai` (local only, nothing pushed). Date 2026-10-21.

## What changed per file
- `duel/assets.py`: `Asset` named tuple (ticker, name, short, kind, exchange, currency). 10 new assets. Old Milan list kept as the commented `MILAN_V1` block.
- `duel/calendar.py`: sessions come from `exchange_calendars` per exchange. Crypto still means every calendar day. `EXTRA_CLOSED` stays as a manual override. `is_milan_open` is gone (the package replaces it).
- `duel/fetch.py`: `EXCHANGES` table (timezone, close, last-candle hour). `is_complete(day, asset, now)` = after close + 15 min local time. `_fill_from_hourly(asset, df)` and `fetch(asset)` take the asset.
- `duel/__main__.py`, `duel/report.py`: pass the `Asset` through. `data.json` assets gain `short`, `exchange`, `currency`.
- `docs/data-contract.md`: the three new keys.
- `.github/workflows/nightly.yml`: `workflow_dispatch` input `backfill` (default "0"); the run step is `--backfill ${{ inputs.backfill || 0 }}`. Cron events have no input, so they run at 0. The YAML was not parsed by a tool (no pyyaml here); I read it by eye only.
- `pyproject.toml`, `uv.lock`: `exchange-calendars` added. `uv sync --frozen` works.
- `tests/test_score.py`: 9 old tests updated to the new signatures, 4 added (Thanksgiving 2026-11-26 for NVDA, Xetra 2026-12-24 for SIE.DE, Milan Easter Monday 2027-03-29 for STMMI.MI, XNYS completeness at 20:10 vs 21:50 UTC on 2026-12-09).

Not touched: site/, design/, docs/artifacts/, data/ (forecasts.jsonl keeps the old Milan rows; they stay in the file but no longer match any ticker in ASSETS), vendor/. Models were not run, smoke was not run, site/data.json was not rebuilt.

## yfinance timezone finding
Hourly bars come back tz-aware in exchange-local time (NVDA `America/New_York`, SIE.DE `Europe/Berlin`, STMMI.MI `Europe/Rome`). NVDA's last candle of a day starts 15:30 local; SIE.DE and STMMI.MI show a 17:00 candle. The existing `tz_localize(None)` drops the zone and keeps local wall time, so `hour >= 15` (XNYS) and `hour >= 17` (XETR, XMIL) are correct without conversion.

## Ticker check (`yf.download(t, period="5d")`, run 2026-10-21 about 10:33 CEST)
| Ticker | Bars | Last bar | Last close |
|---|---|---|---|
| NVDA | 5 | 2026-10-20 | 216.47 |
| MSFT | 5 | 2026-10-20 | 531.87 |
| GOOGL | 5 | 2026-10-20 | 340.28 |
| AMZN | 5 | 2026-10-20 | 262.63 |
| META | 5 | 2026-10-20 | 694.25 |
| TSM | 5 | 2026-10-20 | 425.08 |
| ASML | 5 | 2026-10-20 | 1630.84 |
| PLTR | 5 | 2026-10-20 | 192.60 |
| SIE.DE | 4 | 2026-10-21 (today, incomplete bar, dropped by `fetch`) | 261.55 |
| STMMI.MI | 4 | 2026-10-21 (today, incomplete bar, dropped by `fetch`) | 41.42 |

All 10 resolve. Nothing written to data/ (the script lived in the scratchpad).

## pytest tail
```
.............                                                            [100%]
13 passed in 1.12s
```

## Old backfill wall time (data/runs.jsonl)
One backfill run: `--backfill 20`, 630 new forecasts, wall 309.5 s (about 5 min), peak RSS 1650 MB, on the old 10 assets. The warm-up for the new set is the same size (10 assets x 21 dates x 3 models = 630), so expect about 5 min of forecasting on a Mac. The GitHub runner (CPU only) was not measured; the workflow timeout is 45 min. Fetching 10 new tickers adds a few seconds.

## Open point
`target_dates` for Milan now follows the package calendar. It agreed with the old hand-written rules for the Dec 2025 and Easter 2026 test cases.
