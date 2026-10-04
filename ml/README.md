# ml/ — forecast pipeline (ml-forecast branch)

Read `docs/ML_TEAM_CONTRACT.md` first. Every number and name comes from `ml/config.py`.

Run order, from the repo root (Python 3.13; `pip install -r ml/requirements.txt`):

```
python ml/src/build_features.py     # data/processed/neighbourhood_monthly.csv -> ml/outputs/features.csv
python ml/src/evaluate.py           # folds A/B, baselines + Poisson GLM + Random Forest -> reports/evaluation.md
python ml/src/forecast.py           # final fit through 2026-08 -> ml/outputs/forecast_2026-10.json, history.json
```

Status 2026-10-03: structure and config only. Scripts are drafted once the contract is confirmed by the ML and data owners.
