# site/data.json keys

Written by `uv run python -m duel run`. The page reads these keys; do not rename them.

- `generated_at`: ISO time (UTC) of the run.
- `models`: model ids, in display order (`kronos`, `timestral`, `naive`).
- `model_info`: per model id, `label`, `params`, `by`.
- `leaderboard`: `live` and `warmup`; each maps model id to `n`, `mape_pct`, `direction_hit_pct`, `beats_naive_pct` (null when n is 0 or for naive).
  `live` counts forecasts made on the newest bar; `warmup` counts backfilled ones.
- `assets`: one entry per ticker with
  - `ticker`, `name`, `short` (short name for tight labels), `kind` (`stock` or `crypto`), `exchange` (exchange_calendars code: `XNYS`, `XETR`, `XMIL`), `currency` (`USD` or `EUR`), `last_close`, `last_date` (last completed bar);
  - `history`: list of `[date, close]` pairs;
  - `latest`: newest forecast set: `made_on`, `dates` (5 target dates), then one list of 5 values per model id (plus `timestral_q10` and `timestral_q90`);
  - `past`: earlier forecasts, each with `made_on`, `live`, `dates`, `actual`, and the model values;
  - `scores`: `live` and `warmup` per model id with `n`, `mape_pct`, `direction_hit_pct`.

## Crowd keys (added on branch crowd-traders)

All three are new top-level keys; no older key changed.

- `crowd`: the Polymarket daily NVDA up/down market read at 09:30 ET (Up price above 0.5 = Up call, below = Down, exactly 0.5 = no call), scored against NVDA's close-to-close move.
  `n` (scored days), `hits`, `direction_hit_pct` (null when n is 0), `no_call` (days at exactly 0.5), `days`: list of `{date, up_price, call, actual, hit}` (`call` and `actual` are `up` or `down`). Unchanged closes are skipped.
- `traders`: `wallets` is the list from `docs/crowd/wallets/index.json` (`wallet`, `trades`, `slugs`, `volume_shares`, `net_up_shares`, `share_days_net_long_up`); `rules` is one entry per rule in `docs/crowd/rules.json`: `id`, `wallet`, `text`, `n`, `hits`, `direction_hit_pct`, `p`, and `in_sample` / `out_of_sample` (each `n`, `hits`, `direction_hit_pct`). A rule that reads only `prior_day_return` also runs on NVDA days before the first crowd day (`out_of_sample`). `rules[].days`: list of `{date, call, actual, hit}` (`call` and `actual` are `up` or `down`), the last 60 scored NVDA days, ascending.
- `luck`: chance of at least that many hits from fair coin flips (`p`, one-sided binomial, null when n is 0). `models`: `live` and `warmup`, each model id to `{n, hits, p}`; `crowd`: `{n, hits, p}`; `rules`: rule id to `{n, hits, p}`.
