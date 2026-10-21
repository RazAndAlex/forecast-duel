# Reach check: Forecast Duel

## Goal
A public GitHub Pages site that, every night, shows Kronos-base vs Timestral-209M vs a naive "tomorrow = today" baseline forecasting the next 5 daily closes of 10 assets (FTSE MIB stocks .MI + BTC-USD), and scores matured forecasts on % error and direction.

## Plan as given
1. Python pipeline (uv project) in /Users/andreirazvanalexandru/Radar Builds/forecast-duel:
   fetch daily candles from Yahoo via yfinance; forecast next 5 steps with Kronos-base (weights NeoQuasar on Hugging Face, code from github.com/shiyu-coder/Kronos, CPU) and Timestral-209M (github.com/mistralai/timestral, CPU) plus naive baseline; append to data/forecasts.jsonl; score matured forecasts (MAE %, direction hit) into data/scores.json; emit site/data.json.
2. Static page in site/ (vanilla HTML+JS, chart per asset, leaderboard), designed by the main session.
3. GitHub Actions nightly cron 00:30 UTC on ubuntu-latest (CPU) runs the pipeline, commits data, deploys to GitHub Pages. Public repo under account RazAndAlex (user OK needed before create/push).
4. Pipeline built by a worker; verified by a different-vendor worker running it end to end.

## Plan (converted)
# Forecast Duel: converted plan

Sources: K=Kronos/model/kronos.py, KR=Kronos/README.md, T=timestral/src/timestral/forecaster.py, TP=timestral/pyproject.toml, Y=yfinance/yfinance/multi.py, D=deploy-pages/README.md, U=setup-uv/README.md.

## 1. Steps
1. `uv init` in forecast-duel. Add deps: `timestral` from `git+https://github.com/mistralai/timestral.git` (TP: torch>=2.4, Python>=3.10, lock: torch 2.14.1, cp314 wheels), `yfinance`, plus Kronos/requirements.txt pins (pandas==2.2.2, huggingface_hub==0.33.1, einops==0.8.1). Kronos has no pyproject: vendor its `model/` dir and import with `from model import Kronos, KronosTokenizer, KronosPredictor` (KR line 108).
2. Run `uv lock --python 3.14`; if pandas==2.2.2 fails, retry with 3.12, record it.
3. fetch.py: `yf.download(tickers, period=..., interval="1d", auto_adjust=True, multi_level_index=...)` (Y line 55) for 9 `.MI` tickers + `BTC-USD`; lowercase columns to open/high/low/close/volume.
4. kronos.py: `KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")`, `Kronos.from_pretrained("NeoQuasar/Kronos-base")` (KR lines 81, 111), `KronosPredictor(model, tokenizer, device="cpu", max_context=512)` (K line 484), then `predictor.predict(df, x_timestamp, y_timestamp, pred_len=5, T, top_p, sample_count)` (K line 519); x/y_timestamp must be pandas Series (`calc_time_stamps` uses `.dt`, K line 472). Take `close`. y_timestamp: next 5 business days (calendar days for BTC-USD).
5. timestral.py: `TimestralForecaster.from_pretrained("mistralai/Timestral-209M", device="cpu")` (T line 123), `forecaster.forecast(context, prediction_length=5)` (T line 161) on close arrays shaped (B,T); read `Forecast.median` (T line 49).
6. naive.py: repeat last close 5 times.
7. store.py: append one JSON line per (date, asset, model, 5 values) to `data/forecasts.jsonl`; score rows whose 5 target dates now have closes from step 3: MAE % and direction hit into `data/scores.json`; write `site/data.json` with `generated_at` and a `model` field per series.
8. Run `uv run python -m <pipeline>` locally on M1 (pass `device="cpu"` to both models; KronosPredictor otherwise auto-picks `mps`, K lines 493-501). Log wall time, peak RAM.
9. site/: index.html + app.js read `data.json`; one chart per asset, leaderboard. Designed by main session.
10. `.github/workflows/nightly.yml`: `on: schedule` cron `30 0 * * *`, `runs-on: ubuntu-latest`; build job: `astral-sh/setup-uv` (U line 30) with `enable-cache`, `uv run` pipeline, `git commit`/`git push` of data/, `actions/upload-pages-artifact` with path site/ (D line 13); deploy job: `needs: build`, `permissions: pages: write, id-token: write`, `environment: github-pages`, `actions/deploy-pages@v4` (D lines 25-44).
11. After user OK: `gh repo create RazAndAlex/forecast-duel --public`, `git push`, set Pages source to GitHub Actions (D line 84).
12. Trigger one run with `gh workflow run nightly.yml`; watch with `gh run watch`.
13. Different-vendor worker: fresh clone, `uv sync`, run step 8 end to end, open the Pages URL.

## 2. Assumptions (unverified)
- pandas==2.2.2 has no Python 3.14 wheel; Kronos works with newer pandas.
- huggingface_hub==0.33.1 satisfies timestral (>=0.23) and Kronos's `from_pretrained`.
- Kronos-base + Timestral-209M (837 MB fp32) fit in 8 GB M1 and in the ubuntu-latest runner RAM, within the job time limit.
- Hub downloads work from Actions without `token`; caching weights needs actions/cache (not read).
- Pushing needs `contents: write` and `actions/checkout` (not read).
- `gh repo create --public`, `gh workflow run`, `gh run watch` flags exist as written (not read).
- yfinance serves .MI and BTC-USD bars to runner IPs.

## 3. Definition of done
`curl -sf https://razandalex.github.io/forecast-duel/data.json | jq -e '(now - (.generated_at|fromdateiso8601) < 129600) and ([.. | objects | .model? // empty] | unique | length == 3)'` exits 0 the morning after the second scheduled run.

## Questions
# Questions for the Forecast Duel plan

## 1. The one observation that would put the goal out of reach
Observation: step 4/5 or the Actions run cannot fetch the two model weights anonymously (gated repo, missing file, or a licence that forbids this use). The whole duel rests on both models loading in an unattended runner with no token (assumption "Hub downloads work from Actions without `token`").
Looked: `curl https://huggingface.co/api/models/<id>`:
- mistralai/Timestral-209M gated=False, files include config.json, model.safetensors
- NeoQuasar/Kronos-base gated=False, files config.json, model.safetensors; Kronos-Tokenizer-base public
- `curl -L .../Timestral-209M/resolve/main/config.json` -> HTTP 200 with no token.
- Licence (Timestral LICENSE, "Modified MIT"): free use unless company revenue > $20M/month. That does not block a personal public site.
Result: holds. Weights are reachable anonymously. I did not run a download in Actions or measure RAM (a model run was forbidden).

## 2. Across-restart boundary (nightly job continuing across days)
What is on the other side: nothing keeps running. Each scheduled run is a new ubuntu-latest VM. No process, connection or model is reattached. No function finds a previous process again. Continuity comes only from (a) GitHub's scheduler starting a new run and (b) records in git (`data/forecasts.jsonl`), which a fresh `actions/checkout` brings back. The second is about records only. For the process side, the one thing that can stop "continuing" is the scheduler itself. GitHub docs (data/reusables/actions/scheduled-workflows-disabled.md): "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days." The plan does not say whether the nightly bot commit counts as activity. I did not verify that.

## 3. Questions
Q1. (Step 2 / assumption "Kronos works with newer pandas") What happens to the plan if this assumption is false? pandas 2.2.2 has no 3.14 wheel, so the 3.14 lock either builds from source or fails, and the fallback depends on Kronos running on whatever pandas resolves.
Evidence: `curl -s https://pypi.org/pypi/pandas/2.2.2/json` -> wheel tags `['cp310','cp311','cp312','cp39','source']`.

Q2. (Step 1 / assumption "huggingface_hub==0.33.1 satisfies timestral") What happens to the plan if this assumption is false? Timestral's own lock was resolved and tested against huggingface_hub 2.2.0, a major version above the Kronos pin, so only the floor `>=0.23` is declared and 0.33.1 is untested by upstream.
Evidence: timestral/uv.lock lines 244-245: `name = "huggingface-hub"` / `version = "2.2.0"`.

Q3. (Step 10 / scheduled workflow over the life of the duel) What happens to the plan if this assumption is false: the nightly bot push counts as "repository activity"? If it does not, the cron stops after 60 days and the site goes stale with no error.
Evidence: GitHub docs scheduled-workflows-disabled.md: "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days."

Q4. (Step 4 / device and load path) Can this step happen at all with what we have? Kronos loads through `PyTorchModelHubMixin.from_pretrained` from huggingface_hub, so the hub version picked in Q2 also decides whether Kronos loads. Pinning 0.33.1 for Kronos and running Timestral on it couples both models to one untested version.
Evidence: Kronos/model/kronos.py line 4 `from huggingface_hub import PyTorchModelHubMixin`; lines 13 and 180 have both classes inherit it.

## Answer (original author's context)
- Step 1 [changed][our code]: do not install Kronos/requirements.txt pins; let timestral's lock pick huggingface_hub/torch/pandas; vendor Kronos `model/`. Answers Q2, Q4.
- Step 2 [changed][our code]: pin Python 3.12 (pandas 2.2.2 wheels stop at cp312, re-run evidence: PyPI tags cp39-cp312). Answers Q1.
- Step 8 [changed][our code]: smoke test loads Kronos via PyTorchModelHubMixin on the resolved hub version and runs one 5-step forecast; if it fails, pin hub to the highest version both accept. Answers Q4.
- Step 10 [changed][our code]: nightly job commits data each run (repository activity) and the README documents `gh workflow enable nightly.yml` as the one-command recovery; the page shows "last updated" so staleness is visible. Answers Q3. Claim "bot push counts as activity" TAKEN AS GIVEN, mitigated by visible staleness.
- Kill observation (anonymous weight download): holds as reachable, taken from questioner's curl evidence (HTTP 200, gated=False).

## Result
GO. All four questions resolved by changed steps. Flag: Q3 claim taken as given on a changed step.
Stop card: budget ~$5 Claude workers; stall rule 3 steps no new evidence; kill question: "if either model cannot load and forecast on CPU in the Actions runner, the goal is out of reach"; progress = a file changed, a passing smoke test, a measured time/RAM.
