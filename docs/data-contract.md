# site/data.json keys

Written by `uv run python -m duel run`. The page reads these keys; do not rename them.

- `generated_at`: ISO time (UTC) of the run.
- `models`: model ids, in display order (`kronos`, `timestral`, `naive`).
- `model_info`: per model id, `label`, `params`, `by`.
- `leaderboard`: `live` and `warmup`; each maps model id to `n`, `mape_pct`, `direction_hit_pct`, `beats_naive_pct` (null when n is 0 or for naive).
  `live` counts forecasts made on the newest bar; `warmup` counts backfilled ones.
- `assets`: one entry per ticker with
  - `ticker`, `name`, `kind` (`stock` or `crypto`), `last_close`, `last_date` (last completed bar);
  - `history`: list of `[date, close]` pairs;
  - `latest`: newest forecast set: `made_on`, `dates` (5 target dates), then one list of 5 values per model id (plus `timestral_q10` and `timestral_q90`);
  - `past`: earlier forecasts, each with `made_on`, `live`, `dates`, `actual`, and the model values;
  - `scores`: `live` and `warmup` per model id with `n`, `mape_pct`, `direction_hit_pct`.
