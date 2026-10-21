# Forecast Duel

**Live page: https://razandalex.github.io/forecast-duel/** (updated every night at 00:30 UTC)

Each night, forecasts the next 5 daily closes of 12 assets with Kronos-base,
Timestral-209M and a naive baseline, scores the matured forecasts, and writes
`site/data.json` for a static page.

## Run locally

```bash
uv sync                       # install dependencies (Python 3.12, CPU torch)
uv run pytest -q              # run the test suite
uv run python -m duel run --backfill 20   # fetch, forecast, score, write site/data.json
```
