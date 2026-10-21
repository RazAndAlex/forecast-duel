# Forecast Duel

**Live page: https://razandalex.github.io/forecast-duel/** (updated every night at 00:30 UTC)

Two AI forecasting models predict stock prices every night, and this project scores them in public.

## The players

**The price duel: 12 stocks, 5 days ahead.**

- **Kronos-base** (Tsinghua, 102M parameters) and **Timestral-209M** (Mistral AI) forecast the next 5 daily closes of 12 AI, chip and industrial stocks. The stocks trade in New York, Frankfurt and Milan.
- **Naive** says that every future close equals the last close. It is the bar to beat.
- The score is the mean miss: the average gap between the forecast and the real close, as a percentage of the price.

**The direction game: NVDA, one day ahead.**

- **The crowd.** Polymarket runs a daily market "NVDA Up or Down" (`nvda-up-or-down-on-<month>-<day>-<year>`). At 09:30 New York time, when the stock market opens, we read the price of "Up". Above 50¢ counts as an Up call, and below 50¢ counts as a Down call. The call is right when NVDA closes above the close of the day before.
- **Three trader rules.** We read every trade in those markets and kept the 8 wallets that trade often: at least 30 trades over at least 10 market days, with market makers removed. We gave a wallet a rule only when one simple habit fits at least 75% of its days. 3 wallets qualify:
  - *Every morning Up*: buys Up before the open every day.
  - *Bet against yesterday*: buys Up after NVDA fell and sells Up after it rose.
  - *Follow the crowd*: buys Up when the price is above 50¢ and sells it when the price is below.

  We replay each rule on NVDA's own closes. The first two rules also run on the days before Polymarket listed the market (572 days at launch). The habits were not drawn from those days, so they are a fair test.
- **The coin test.** For every player, including the models, the page shows how often a coin flip gets as many directions right by luck. A result below 1 in 20 shows in bold.

The crowd has one advantage: at 09:30 it can already see NVDA's trading before the open. The models forecast from the close of the night before.

## How it runs

A GitHub Actions job (`.github/workflows/nightly.yml`) runs every night at 00:30 UTC. It does these steps:

1. Fetches the prices.
2. Makes new forecasts.
3. Scores the forecasts whose days have closed.
4. Reads the day's crowd price from Polymarket.
5. Writes `site/data.json` and publishes the page.

If Polymarket does not answer, the job continues without the crowd for that day.

The wallet tables and the trader rules do not change every night. You update them by hand (see below).

## Run locally

```bash
uv sync                                   # install dependencies (Python 3.12, CPU torch)
uv run pytest -q                          # run the test suite
uv run python -m duel run --backfill 20   # fetch, forecast, score, write site/data.json
uv run python -m duel.traders             # re-read the wallets into docs/crowd/wallets/
```

The rules are in `docs/crowd/rules.json`. The fields of `site/data.json` are in `docs/data-contract.md`.
