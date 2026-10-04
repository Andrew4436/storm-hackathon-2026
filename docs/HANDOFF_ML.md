# ML hand-off for Chibueze (and Codex)

Written 2026-10-04, early morning, after the overnight integration. This is the catch-up for the `ml/` and
`reports/` folders. Read it top to bottom once; the first section is the summary an assistant should keep in
context.

## 1. Main points

- **`main` is the release.** Everything below is on `origin/main`. Your `ml-forecast` branch was merged into it
  and is now behind; work from `main` from here on (`git checkout main && git pull`). Do not rebase or force-push
  anything.
- **The Poisson GLM is still the shipped model.** Five alternatives were tested under a rule written before the
  run (per-type GLMs, an extended-feature GLM, gradient boosting, a stacked blend, per-area bias correction). None
  beat the GLM on the most recent year, so none shipped. Details in `reports/model_study.md`.
- **Hard tiers are gone from the product.** The pipeline now outputs calibrated probabilities per area:
  `p_below`, `p_within`, `p_above` (chance the month ends more than 10% below, within 10% of, or more than 10%
  above the area's level in the same month one year earlier). The map colours continuously by
  `p_above - p_below`. The old label survives only as `most_likely` / `relative_activity_tier` for compatibility.
- **The reference level is seasonal:** `TIER_WINDOW_MONTHS = 12`, `tier_reference = "seasonal"`, band
  `TIER_THRESHOLDS_PCT = (-10, 10)`. For the October 2026 forecast the reference is October 2025. History,
  backtest and forecast all use the same rule in `ml/src/tiers.py`.
- **The severity weights are now the official Statistics Canada CSI values** (85-004-X, 2009, Table 1), cited in
  `ml/config.py` and `ml/README.md`. Relative weights barely changed; the index scale rose about 27%, so every
  weighted-index number is larger than before.
- **`ml/outputs/meta.json` is the single source of every number the app and the docs show.** If you change the
  pipeline, regenerate everything with the three commands and run `npm run sync-data` in `crime-tracker/`.
- **Your `FORECAST_MONTH = "2026-010"` typo is fixed** (`"2026-10"`).
- **Model accuracy did not improve and will not with this data alone.** More than half of the remaining error is
  month-to-month randomness in the counts. Say this plainly in the pitch; it is a strength, not a weakness.

## 2. What changed since your last commit (`b89dd3e`)

| Area | Change | Where |
|---|---|---|
| Config | `FORECAST_MONTH` typo fixed; `TIER_WINDOW_MONTHS` 12; thresholds (-10, 10); `TIER_REFERENCE = "seasonal"`; `SEVERITY_WEIGHTS` set to the StatCan values with a per-type mapping comment and source URL; study settings added | `ml/config.py` |
| Study | Pre-registered comparison of five candidates with a fixed selection rule; results and decision written before and after | `ml/src/study.py`, `ml/src/candidates.py`, `ml/src/train_pertype.py`, `ml/src/train_hgb.py`, `reports/model_study.md`, `ml/outputs/study_results.csv`, `ml/outputs/study_decision.json` |
| Tiers | Grid search over window {12, 24, 36} x band {5, 8, 10} x reference {trailing mean, seasonal}; chosen by a stated rule with a disclosed fallback; one `tiers.py` for history, backtest and forecast | `ml/src/tiers.py`, `ml/outputs/tier_study_results.csv` |
| Probabilities | New module: Gaussian kernel on the log of the 480 pooled backtest ratios (bandwidth 0.107, Scott's rule); lognormal tested and rejected (worse Brier) | `ml/src/probabilities.py` |
| Evaluation | Proper scores for the probabilities (Brier for above and below, ranked probability score) against base-rate and hard-label baselines, out of sample in both directions (2025 ratios on 2026 and vice versa); 5-bin reliability tables; tier metrics kept as "most-likely label, for reference" with the majority-class baseline | `ml/src/metrics.py`, `ml/src/evaluate.py`, `ml/outputs/evaluation.json`, `ml/outputs/probability_reliability.csv`, `reports/evaluation.md` |
| Forecast | Records gain `p_above`, `p_below`, `p_within`, `most_likely`, `typical_weighted_index`, and count-target probabilities `p_above_count`, `p_below_count`, `p_within_count` | `ml/src/forecast.py`, `ml/outputs/forecast_2026-10.json`, `.csv` |
| Meta | New file carrying every number the UI shows, plus `tier_mode`, `probability_method`, `weights_source`, `evaluation.probabilistic` | `ml/outputs/meta.json` |
| Docs | README rewritten; contract updated (decisions 2, 4, 5; sections 6, 7, 8; change log) | `ml/README.md`, `docs/ML_TEAM_CONTRACT.md` |

Files that no longer exist on `main`: `scripts/weighted_index_dataset.py`, `ml/src/forecast_raw_counts.py`,
`data/raw/vpd_incidents.csv`, the old weighted-index CSVs. The root `crimedata_csv_AllNeighbourhoods_AllYears.csv`
(no 2022) was removed too; the source is `data/raw/vancouver_crime_data.csv`.

## 3. Current numbers (all out of sample, horizon 2, 24 areas)

Test periods: fold A = 2025-01..2025-12 (288 rows), fold B = 2026-01..2026-08 (192 rows), trained from 2010.

**Point forecast, weighted index (pooled MAE)**

| Method | Pooled | Fold B (2026) |
|---|---|---|
| 12-month mean | 745.5 | 630.2 |
| Poisson GLM (shipped) | 713.1 | 673.1 |
| Random Forest | 775.4 | |
| Closest study candidate (extended GLM) | 720.0 | 681.8 |

GLM is 4.3% better than the 12-month mean pooled, better in 14 of 24 areas, and loses on 2026 alone. On plain
counts: 13.3 vs 13.7 incidents per area-month. WAPE 12.9%.

**Uncertainty range:** 80% range from pooled backtest ratios (multipliers 0.658 to 1.368 on the forecast). Built
on 2025, tested on 2026: covered 79.7%.

**Probabilities (ratios from 2025 applied to 2026, 184 rows, Musqueam excluded)**

| Score | Shipped (kernel) | Base rates | Hard label |
|---|---|---|---|
| Brier, above | 0.160 | 0.239 | 0.255 |
| Brier, below | 0.186 | 0.242 | 0.272 |
| Ranked probability score | 0.173 | 0.241 | 0.264 |

Reliability, above event: said 80-100% -> happened 90% (21 cases); 60-80% -> 75%; 40-60% -> 50%; 20-40% -> 17%
(the weak bin); 0-20% -> 16%. Below event: 80-100% -> 71% (only 14 cases); the rest within 5 points.

**Most-likely label, for reference only:** accuracy 58.9% vs 42.4% majority baseline; macro-F1 0.583;
precision/recall for above about 0.69/0.63, for below 0.71/0.57, for within 0.38/0.56. With a hard label no
October 2026 area would be "typical" because the 10% band is narrower than the forecast error; that is why the
product moved to probabilities.

**Noise floor:** for the median area (about 66 incidents a month) Poisson noise alone is about 12% of a month's
count, about 16% of the weighted index. A forecast that knew each area's true monthly rate would still miss by
about 7 incidents; by that estimate more than half of the remaining error is irreducible.

## 4. The data contract the rest of the team consumes

`ml/outputs/forecast_2026-10.json`, one object per area:

```
neighbourhood, month ("2026-10"), mode ("forecast"),
forecast_weighted_index, forecast_incident_count, interval_low, interval_high,
typical_weighted_index, pct_vs_typical, baseline_weighted_index,
p_below, p_within, p_above (sum to 1.000; null for insufficient_data),
most_likely ("above_typical" | "below_typical" | "typical" | "insufficient_data"),
relative_activity_tier (= most_likely, compatibility only),
p_below_count, p_within_count, p_above_count,
drivers (list; not displayed any more), data_through ("2026-08"), horizon_months (2), model ("poisson_glm")
```

`ml/outputs/history.json`, 6,840 objects: `neighbourhood, month, weighted_index, incident_count,
pct_vs_typical (null where no reference, partial month, or Musqueam), relative_activity_tier (used only to detect
insufficient_data), is_partial`.

`ml/outputs/meta.json`: `app, model, model_description, data_through, forecast_month, horizon_months,
tier_window_months, tier_thresholds_pct, tier_reference, tier_mode ("probabilistic"), probability_method,
interval_level, evaluation {folds, pooled_mae_weighted_index {mean_12, previous_glm, shipped},
improvement_vs_mean_12_pct, improvement_vs_previous_pct, wape_pct, interval_coverage_pct, tier_accuracy_pct,
tier_majority_baseline_pct, tier_macro_f1, probabilistic {brier_above, brier_below, brier_above_baseline,
brier_below_baseline, rps, rps_baseline, rps_hard_tier, reliability_above[], reliability_below[], statement,
scored_on}}, weights_source, generated_from, notes[]`.

Consumers: `backend/app.py` loads these three files at startup and serves them unchanged
(`/meta`, `/history`, `/forecast`); `crime-tracker/` reads them from `public/data/` after `npm run sync-data`.

## 5. How to run and how to change things

```
python ml/src/build_features.py    # processed csv -> ml/outputs/features.csv, history.csv/json
python ml/src/evaluate.py          # study + backtest + proper scores -> reports/*.md, evaluation.json, metrics
python ml/src/forecast.py          # final fit -> forecast_2026-10.json/csv, meta.json, history.json
cd crime-tracker && npm run sync-data   # copies meta.json, history.json, forecast_<month>.json into public/data
```

Whole pipeline about 70 to 105 seconds, deterministic (two runs give byte-identical files). Scripts run from any
working directory. Every setting lives in `ml/config.py`; scripts never hard-code a month, window, weight or
threshold.

Rules that keep it trustworthy:

- Never use 2026-09 (partial) as a feature source, a target, or "the latest month". `DATA_THROUGH` is 2026-08.
- Never de-duplicate raw rows; never zero-fill a month that was not published. (Both handled upstream in `data/`.)
- Do not change the selection rule after seeing results. If you add a candidate, add it to `candidates.py`,
  rerun the study, and let the rule decide.
- If you change weights, the window, the band or the reference, regenerate all three steps and sync the frontend;
  the docs that quote numbers are `README.md`, `docs/DEVPOST.md`, `docs/PITCH.md`, `docs/VIDEO_SCRIPT.md`,
  `docs/ML_TEAM_CONTRACT.md`.
- Commit the generated outputs; the frontend and backend read them from the repo.

## 6. Known rough edges (none block the demo)

- `meta.json` rounds `tier_macro_f1` to 0.584; the reports say 0.583 (raw 0.58347). Nothing on screen shows it.
- `meta.json` `probability_method` is a sentence; the frontend only maps the keys `kde` / `lognormal` to a friendly
  name, so the method sentence is simply not shown. `evaluation.json` has `probabilistic.method = "kde"`.
- In the 2026->2025 direction the 80-100% "above" bin happened 65% of the time (n = 20). The headline uses
  2025->2026. Both directions are in `reports/evaluation.md`.
- When no candidate qualified, the parent for the C5 bias-correction candidate was picked by pooled MAE, which
  includes fold B. It had no effect on the outcome (C5 did not qualify either).
- The tier grid search had no cell meeting both pre-registered constraints; the fallback (keep the readable-map
  constraint, drop the history-share constraint, take the highest skill) is disclosed in the report.
- The StatCan weights are the 2009 published table; no public table of the current weights was found. The weakest
  mapping is Offence Against a Person -> assault level 2 (the VPD category mixes assaults, robbery and sexual
  offences).
- Musqueam has null probabilities and null `pct_vs_typical` on purpose (insufficient data, about 2 incidents a
  month).

## 7. For the technical part of the pitch

- "We forecast the expected level two months ahead. Our error, 12.9% of volume, is at the noise floor of monthly
  counts, so we show a calibrated range and probabilities instead of a point."
- "We pre-registered the rule, tested five alternatives, and shipped the simplest model because none of them beat
  it on the most recent year."
- "When we said 80 to 100% chance a month would run above its level a year earlier, it happened 90% of the time.
  Our ranked probability score is 28% better than using base rates."
- Be ready for: why 2022 was missing (recovered from a separate download), why no street level (noise and the VPD
  disclaimer), why Musqueam has no colour, why the 12-month mean wins on 2026 alone (level shift in 2026), where the
  weights come from (StatCan 85-004-X Table 1).

## 8. Your checklist today

1. `git checkout main && git pull`. Run the three commands once to confirm the outputs regenerate on your machine.
2. Read `reports/evaluation.md` and `reports/model_study.md`; they are what you will be asked about.
3. Decide with the team whether to show both `p_above` and `p_above_count` anywhere; today only the weighted index
   probabilities are displayed.
4. If you touch anything in `ml/`, rerun all three steps, `npm run sync-data`, and tell whoever is deploying.
