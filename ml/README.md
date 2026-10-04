# ml/ — forecast pipeline (ml-forecast branch)

Read `docs/ML_TEAM_CONTRACT.md` first. Every number and name comes from `ml/config.py`.

Run order, from the repo root (Python 3.13; `pip install -r ml/requirements.txt`). Scripts also work from any
other working directory. The whole pipeline takes about 30 seconds and is deterministic (re-runs give
byte-identical files).

```
python ml/src/build_features.py     # data/processed/neighbourhood_monthly.csv -> ml/outputs/features.csv, history.csv
python ml/src/evaluate.py           # folds A/B, baselines + Poisson GLM + Random Forest -> reports/evaluation.md, evaluation.json
python ml/src/forecast.py           # final fit through 2026-08 -> ml/outputs/forecast_2026-10.json/.csv, history.json
```

`forecast.py` reads the model decision and backtest predictions written by `evaluate.py`, so keep the order.

| file | what it does |
|---|---|
| `config.py` | all numbers: weights, horizon, folds, model params, tier window and thresholds |
| `src/common.py` | repo paths, loads the processed csv and computes `weighted_index` from the weights |
| `src/build_features.py` | lag features for both targets (`wi_*`, `ic_*`) -> `outputs/features.csv`; per-month tiers -> `outputs/history.csv` |
| `src/baselines.py` | 3-month mean, 12-month mean, same month last year |
| `src/train_poisson.py` | Poisson GLM on log1p features + month one-hot (optional area one-hot); `month_effects()` for drivers |
| `src/train_rf.py` | Random Forest on raw features + area code; tree-spread interval for comparison only |
| `src/tiers.py` | tier rule and trailing 36-month "typical" mean, shared by history, evaluation and forecast |
| `src/intervals.py` | 80% range from pooled backtest ratios actual / forecast |
| `src/evaluate.py` | backtest on identical rows, metrics, model decision -> `outputs/evaluation_metrics.csv`, `backtest_predictions.csv`, `evaluation.json`, `reports/evaluation.md` |
| `src/forecast.py` | final fit, forecast, intervals, tiers, drivers -> `outputs/forecast_2026-10.{csv,json}`, `outputs/history.json`; fills the tier-distribution section of `reports/evaluation.md` |

Tier thresholds (`TIER_THRESHOLDS_PCT`) are tuned by the team at the 7 PM checkpoint; after changing them, re-run all three steps.
