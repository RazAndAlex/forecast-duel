[summary]
- Bug 1 cause: Kronos context length. Columns, amount, timestamps and sample averaging were all correct and the vendored code equals upstream. With 512 daily bars Kronos drifts 10-30% (ENI day 1 -13%); with 150 bars every asset stays within 4%.
- Bug 1 fix: `run_one` in duel/__main__.py feeds Kronos the last 150 bars. Not tested at other settings beyond 150/250/300/350/400/512.
- Bug 2 cause: Yahoo's daily feed has no 2026-10-20 bar for .MI stocks (with or without `end=`); its hourly feed has it. The old code never saw the bar.
- Bug 2 fix: duel/fetch.py rebuilds missing sessions from hourly bars and applies the completeness rule `is_complete` (stocks: before today Rome, or from 17:45 Rome; BTC: before today UTC). Stock last_date is now 2026-10-20.
- Backfill 20: wall 309.5 s, peak RSS 1650 MB (data/runs.jsonl), 630 forecasts.
- Warm-up n: kronos 160, timestral 160, naive 160 (MAPE 3.44 / 2.48 / 2.43 %).
- pytest: 5 passed, including the completeness test.

## Kronos day-1 sanity (live forecast made on 2026-10-20)
| Asset | Last close | Kronos day 1 | Move |
|---|---|---|---|
| BTC-USD | 82941.0 | 82901.4 | -0.05% |
| ENEL.MI | 9.194 | 9.134 | -0.65% |
| ENI.MI | 25.96 | 25.526 | -1.67% |
| G.MI | 42.16 | 42.211 | +0.12% |
| ISP.MI | 5.989 | 5.958 | -0.51% |
| LDO.MI | 49.215 | 49.189 | -0.05% |
| RACE.MI | 356.15 | 355.331 | -0.23% |
| STLAM.MI | 3.836 | 3.772 | -1.68% |
| TIT.MI | 5.636 | 5.582 | -0.96% |
| UCG.MI | 74.19 | 74.912 | +0.97% |

Worst day-1 move across all 20 backfill dates per asset: 3.78% (TIT.MI). All under 8%.

## Details
- Repro script: scratchpad repro.py / repro2.py (not in project). Day-1/day-5 moves by context length, sample_count 5: ENI 150 bars -1.5%/-6.5%, 512 bars about -13%/-30%; STLAM 150 bars -2.4%/+4.9%, 300 bars +2.3%/+42%.
- Inference, not tested: the long window pulls in price levels from a year earlier, so Kronos extrapolates a regime change. I did not test why.
- Stock closes for rebuilt sessions come from the last hourly bar of the day (approximates the closing auction); the 10-20 close for ENI is 25.96.
- Changed files: duel/fetch.py, duel/__main__.py, tests/test_score.py, docs/data-contract.md. Deleted and rebuilt: data/forecasts.jsonl, data/runs.jsonl.
- Decision logged: 150 bars. Tested 150, 250, 300, 350 on all 10 assets, and 200 on two. 150 had the smallest drift everywhere (day 5 within 7%).
