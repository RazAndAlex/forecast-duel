# Fix report: three verifier findings

Date: 2026-10-21. No commit, no push. `uv run pytest`: 9 passed.

| # | Fix | Where | Test (failed before, passes after) |
| --- | --- | --- | --- |
| 1 | Stock targets follow the Milan calendar; scoring uses the same dates | new `duel/calendar.py` (`target_dates` moved there), `duel/report.py` `_actual_after` | `test_stock_targets_skip_borsa_holidays`, `test_scoring_needs_real_target_dates` |
| 2 | Cached CSV reload parses floats exactly | `duel/fetch.py` `load_cached` (`float_precision="round_trip"`) | `test_csv_reload_keeps_floats` |
| 3 | Hourly fallback accepts a day only if its last candle starts at 17:00 local or later | `duel/fetch.py` `_fill_from_hourly` | `test_hourly_fallback_rejects_partial_day` |

## Choices
- Holidays: a rule list, with no new dependency. Fixed closures (1 Jan, 1 May, 15 Aug, 24/25/26/31 Dec) plus Good Friday and Easter Monday from `dateutil.easter` (ships with pandas). `exchange_calendars` would add a package to the lockfile and the GitHub workflow. Limit: one-off closures go in `EXTRA_CLOSED`.
- Scoring: the 5 closes on the calendar target dates after made_on. If any is missing, the forecast stays unscored. This replaces "next 5 bars in the CSV". BTC is unchanged (7 days a week).
- Legacy forecasts keep their stored `dates` and values. Kronos forecasts made across a holiday used the old timestamps as model input; those are not redone.
- Float: the CSV was already written exactly; only the read was lossy.

## Warm-up leaderboard, rebuilt from cached data
| Model | MAPE before | MAPE after | Direction before | Direction after |
| --- | ---: | ---: | ---: | ---: |
| Kronos | 3.44 | 3.44 | 42.5 | 42.5 |
| Timestral | 2.48 | 2.48 | 40.62 | 40.62 |
| Naive | 2.43 | 2.43 | 36.88 | 36.88 |

n stays 160 per model. The "before" column is the stored `site/data.json`. Without fix 2, a rebuild gave naive 37.50.

Check number: naive direction_hit is 36.88 from the raw stdlib-parsed CSVs and 36.88 from the reloaded CSVs.

Touched outside code: `site/data.json` only (new `generated_at`; scores unchanged). `data/prices/` untouched.

Not checked: live Yahoo hourly timestamps. The fix assumes the index carries Milan local time, as the old `tz_localize(None)` also did.
