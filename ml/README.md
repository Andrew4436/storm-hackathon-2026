# ml/ — forecast pipeline (ml-forecast branch)

Read `docs/ML_TEAM_CONTRACT.md` first. Every number and name comes from `ml/config.py`.

Run order, from the repo root (Python 3.13; `pip install -r ml/requirements.txt`). Scripts also work from any
other working directory. The whole pipeline takes about 40 seconds and is deterministic (re-runs give
byte-identical files).

```
python ml/src/build_features.py     # data/processed/neighbourhood_monthly.csv -> ml/outputs/features.csv, history.csv
python ml/src/evaluate.py           # backtest of all methods + model/tier studies -> reports/evaluation.md, reports/model_study.md, evaluation.json
python ml/src/forecast.py           # final fit through 2026-08 -> ml/outputs/forecast_2026-10.json/.csv, history.json, meta.json
```

`evaluate.py` runs the model and tier studies (`study.py`) itself, so these three commands regenerate everything.
`python ml/src/study.py` runs the studies alone (about 30 s) if you only want `reports/model_study.md`.
`forecast.py` reads the model decision and backtest predictions written by `evaluate.py`, so keep the order.
After changing anything in `config.py` (weights, tier settings), re-run all three.

| file | what it does |
|---|---|
| `config.py` | all numbers: weights (cited), horizon, folds, selection rule, model params, tier window / thresholds / reference |
| `src/common.py` | repo paths, loads the processed csv and computes `weighted_index` from the weights |
| `src/build_features.py` | lag features for both targets (`wi_*`, `ic_*`), long windows, city momentum, per-type lags -> `outputs/features.csv`; tiers -> `outputs/history.csv` |
| `src/baselines.py` | 3-month mean, 12-month mean, same month last year |
| `src/train_poisson.py` | Poisson GLM: C0 (shipped, `base`) and C2 (`extended` features); `month_effects()` for drivers |
| `src/train_pertype.py` | C1: one Poisson GLM per incident type, summed with the severity weights |
| `src/train_hgb.py` | C3: Poisson gradient boosting with time-ordered early stopping |
| `src/train_rf.py` | Random Forest on raw features + area code; tree-spread interval for comparison only |
| `src/candidates.py` | registry of every method, backtest on identical rows, C4 stacking, C5 area correction, the selection rule, final fit |
| `src/metrics.py` | regression, tier, paired-month and noise-floor metrics |
| `src/study.py` | model study + tier grid -> `reports/model_study.md`, `outputs/study_results.csv`, `outputs/tier_study_results.csv`, `outputs/study_decision.json` |
| `src/tiers.py` | the one tier rule (window, thresholds, trailing or seasonal reference) used by history, backtest, study and forecast |
| `src/intervals.py` | 80% range from pooled backtest ratios actual / forecast |
| `src/evaluate.py` | metrics, decision, `outputs/evaluation_metrics.csv`, `backtest_predictions.csv`, `evaluation.json`, `reports/evaluation.md` |
| `src/forecast.py` | final fit, forecast, intervals, tiers, drivers -> `outputs/forecast_2026-10.{csv,json}`, `outputs/history.json`, `outputs/meta.json` |

Outputs for the app: `forecast_2026-10.json` (contract fields plus an additive `typical_weighted_index`, the level
`pct_vs_typical` is measured against; `baseline_weighted_index` is still the 12-month mean), `history.json`, and
`meta.json` (model name, evaluation headline numbers, tier settings, weights source, notes).

## Model choice

The shipped model is chosen by a rule fixed before the study (`config.SELECTION_*`, `reports/model_study.md`):
a candidate must beat the 2026-10-03 Poisson GLM by at least 1% on the most recent fold (2026) and on the pooled
MAE. On 2026-10-04 none of five candidates (per-type GLMs, extended GLM, gradient boosting, stacking, per-area
correction) qualified, so the Poisson GLM stays.

## Tiers

`relative_activity_tier` compares a month with the same calendar month one year earlier (window 12, seasonal
reference, +-10%). This was picked from an 18-cell grid (`reports/model_study.md`) by tier skill over the
always-guess-the-most-common-tier baseline, keeping a readable 2026-10 map. History, backtest and forecast use the
same `tiers.py` rule, so `history.json` and the forecast always agree.

## Severity weights

`weighted_index` is **CSI-inspired, not Statistics Canada's official Crime Severity Index**: the official CSI covers
almost all Criminal Code offences, uses weights that StatCan updates periodically, and divides by population; we
weight only the 8 VPD types kept in the processed data, per neighbourhood-month, with no population denominator.
The weights are the published values in Statistics Canada, *Measuring Crime in Canada: Introducing the Crime Severity
Index and Improvements to the Uniform Crime Reporting Survey* (catalogue 85-004-X, 2009), Table 1 "Examples of
weights for the Crime Severity Index" (<https://www150.statcan.gc.ca/n1/pub/85-004-x/2009001/t001-eng.htm>), based
on 2002/03..2006/07 court sentencing data; we did not find a public table of the current weights. Mapping:
Other Theft, Theft from Vehicle and Theft of Bicycle -> "Theft under $5,000" (37); Mischief -> "Mischief" (30);
Break and Enter Residential/Other and Break and Enter Commercial -> "Breaking and entering" (187); Theft of Vehicle ->
"Theft of a motor vehicle" (84); Offence Against a Person -> "Assault - level 2" (77). The last mapping is the weakest:
the VPD category mixes assault levels 1-3 (23 / 77 / 405), robbery (583) and sexual offences, and its composition
is not published per neighbourhood, so a mid-range violent weight close to the CSI average (69) was used. Until
2026-10-03 the working values were these weights x ~0.79 (29/29/24/60/147/147/66/29); switching to the published
values changed relative weights by under 2% and raised the index scale by about 27%.
