# ML team contract: Vancouver neighbourhood incident forecast

Written 2026-10-03 (StormHacks 2026, deadline Sunday 12:00 PM PDT); updated 2026-10-04 to match the final pipeline
(see the change log at the end). This is the single source of truth for the `data-pipeline` and `ml-forecast` branches. It is written for teammates AND for their AI assistants (Cursor, Codex,
Claude Code). If anything you know contradicts this file, say so before writing code; we fix the contract, then the code.

## 1. What we are building

A map of Vancouver's 24 VPD neighbourhoods. Historical mode shows reported-incident activity per neighbourhood per
month. Forecast mode shows a forecast for **October 2026** with an uncertainty range and a tier relative to that
neighbourhood's own history. No place is judged or rated (wording rules in decision 7). Unit of everything:
**one neighbourhood x one calendar month**.

## 2. Decisions (firm unless the team changes this file)

1. **Data file:** `data/processed/neighbourhood_monthly.csv` on `main`, produced by `data/stormhacks2026_data_cleaning.ipynb`.
   Nobody re-cleans raw data in `ml/`. The old `data/raw/vpd_incidents.csv` and `scripts/weighted_index_dataset.py`
   on `ml-forecast` are retired (they used the export that is missing 2022).
2. **Target:** `weighted_index` = sum over the 8 included types of (monthly count x severity weight).
   The weights are the official published values in Statistics Canada, *Measuring Crime in Canada: Introducing the
   Crime Severity Index and Improvements to the Uniform Crime Reporting Survey* (catalogue 85-004-X, 2009), Table 1
   "Examples of weights for the Crime Severity Index",
   <https://www150.statcan.gc.ca/n1/pub/85-004-x/2009001/t001-eng.htm> (weights from 2002/03..2006/07 court
   sentencing data). They live in `ml/config.py` (`SEVERITY_WEIGHTS`, cited line by line, plus `WEIGHTS_SOURCE`);
   the mapping is explained in `ml/README.md`, "Severity weights":

   | VPD type | CSI offence category | weight |
   |---|---|---|
   | Other Theft, Theft from Vehicle, Theft of Bicycle | Theft under $5,000 | 37 |
   | Mischief | Mischief | 30 |
   | Offence Against a Person | Assault - level 2 (weakest mapping: the VPD type mixes assault levels 1-3, robbery and sexual offences; 77 is close to the CSI average weight) | 77 |
   | Break and Enter Residential/Other, Break and Enter Commercial | Breaking and entering | 187 |
   | Theft of Vehicle | Theft of a motor vehicle | 84 |

   The index is **CSI-inspired, not the official CSI**: the official CSI covers almost all Criminal Code offences,
   uses weights StatCan updates periodically and divides by population; we weight 8 VPD types per
   neighbourhood-month with no population denominator. We did not find a public table of the current weights.
   `incident_count` (unweighted) is forecast by the same code as a secondary output, because judges and users
   understand "about 95 reported incidents" more easily than an index value.
3. **Horizon:** forecast month 2026-10 from data through **2026-08** (horizon = 2). 2026-09 is partial and is never a
   feature source, a training target, or "the latest month".
4. **Models:** Poisson GLM and Random Forest, both implemented, both evaluated on identical rows against three
   baselines. The shipped model is whichever has the lower pooled MAE on `weighted_index`; this rule is fixed now,
   before the final run. A 50/50 blend of the GLM and the 12-month mean is also reported.
   **Outcome.** The GLM won that comparison (pooled `weighted_index` MAE 713.1 vs 775.4 for the Random Forest, with
   the final weights). On 2026-10-04 a second rule was fixed before a model study was run (`config.SELECTION_*`,
   `reports/model_study.md`): a candidate replaces the GLM (C0) only if its `weighted_index` MAE is at least 1% lower
   than C0's on fold B (2026) AND lower pooled over both folds; among qualifiers the lowest pooled MAE ships, and a
   simpler qualifier within 1% wins the tie; if nothing qualifies, C0 stays. Candidates: C1 per-type GLMs summed with
   the weights, C2 extended-feature GLM, C3 Poisson gradient boosting (C3b: its 50/50 blend with C2), C4 stacked
   blend, C5 per-area bias correction; everything tuned was tuned on fold A only. **Result: no candidate qualified,
   so the Poisson GLM ships** (`model = "poisson_glm"`). The closest, C2, was 1.3% worse than C0 on fold B and 1.0%
   worse pooled.
5. **Tiers:** `below_typical` / `typical` / `above_typical`, computed per neighbourhood against a **seasonal**
   reference: the same calendar month within the last `TIER_WINDOW_MONTHS` (12) complete months, i.e. the same month
   one year earlier (`TIER_REFERENCE = "seasonal"`). Thresholds `TIER_THRESHOLDS_PCT = (-10, +10)`: more than 10%
   below the reference is `below_typical`, more than 10% above it is `above_typical`, otherwise `typical`. Areas
   averaging fewer than `TIER_MIN_MEAN` (10) incidents a month are `insufficient_data` (Musqueam). One function,
   `ml/src/tiers.py`, applies the rule identically to history, backtest and forecast, so `history.json` and the
   forecast always agree. Each forecast record carries the reference level as `typical_weighted_index`.
   The setting was chosen by the pre-registered grid search in `reports/model_study.md` ("Tier decision"): window
   {12, 24, 36} months x thresholds {+-5, +-8, +-10}% x reference {trailing mean, seasonal}; highest skill
   (macro-F1 minus the accuracy of always guessing the most common tier), subject to (a) at least 3 areas below and
   3 above in the 2026-10 forecast and (b) 30-60% of history months `typical`. **Fallback, disclosed:** no cell met
   both constraints, so a fallback added after seeing the grid keeps (a), drops (b) and takes the highest skill; the
   pick has 25% `typical` history months. Without either constraint the same cell has the highest skill in the grid.
   Every trailing-mean setting, including the 2026-10-03 rule (36 months, +-5%), had negative skill. A single-month
   reference is noisy, so part of the tier skill is regression to the mean.
6. **Uncertainty:** an 80% range from backtest error ratios (actual / forecast) pooled across neighbourhoods.
   Not from Random Forest tree spread (it covered 66% at a nominal 80% in our test and depends on `min_samples_leaf`).
7. **Wording:** "reported incidents", "severity-weighted activity", "relative to this area's own history",
   "uncertainty range". Never "crime risk", "safety score", "safe", "unsafe", "dangerous", "predict crime".

## 3. Data facts every assistant must know

- Raw source: VPD GeoDASH open data. The all-years export is missing 2022; a separate 2022 download was merged in.
  Data runs 2003-01-01 to **2026-09-25**. September 2026 has about 70% of a normal month's rows (`is_partial = 1`).
- Cleaning already done (see `data/README.md`): 106 blank-neighbourhood rows dropped; Homicide and both Vehicle
  Collision types dropped (collisions have a 5x recording jump in 2014; homicide is about 1/month city-wide);
  **no de-duplication** (42% of Offence Against a Person rows are exact copies by design because VPD redacts their
  time and location); full 24 x 285 grid with true zeros (18 cells, all Musqueam).
- The 8 types kept: Other Theft, Theft from Vehicle, Mischief, Offence Against a Person,
  Break and Enter Residential/Other, Break and Enter Commercial, Theft of Vehicle, Theft of Bicycle.
- Map join: VPD "Central Business District" = City of Vancouver polygon "Downtown"; Stanley Park has no polygon
  (marker); Musqueam sits inside Dunbar-Southlands, averages about 2 incidents/month, shows "insufficient data".
- Known traps: never fill a missing month with 0 unless it was actually published; never derive neighbourhood from
  X/Y; Offence Against a Person has a reporting lag, so recent months are under-reported.

## 4. Processed schema (data-pipeline delivers; ML consumes)

`data/processed/neighbourhood_monthly.csv`, one row per neighbourhood-month, 6,840 rows:

| column | type | meaning |
|---|---|---|
| `year`, `month` | int | calendar year, month number 1-12 |
| `month_str` | str | `YYYY-MM`, the team's month key |
| `neighbourhood` | str | VPD name, 24 values |
| `incident_count` | int | sum of the 8 types |
| `other_theft`, `theft_from_vehicle`, `mischief`, `offence_against_a_person`, `break_and_enter_residential_other`, `break_and_enter_commercial`, `theft_of_vehicle`, `theft_of_bicycle` | int | per-type counts (**being added** by data-pipeline; needed for the weighted index) |
| `is_partial` | 0/1 | 1 only for 2026-09 |

ML computes `weighted_index` from the per-type columns using `ml/config.py`. The weights live in one place only.

## 5. Features (all known at the origin month t; target is month t+2)

| feature | definition |
|---|---|
| `last_value` | value at t |
| `mean_3`, `mean_6`, `mean_12` | mean of t-2..t, t-5..t, t-11..t |
| `same_month_last_year` | value at target month minus 12 |
| `target_month_number` | calendar month of the target, 1-12 (one-hot for the GLM) |
| `neighbourhood` | one-hot for the GLM (optional, test both), category code for the forest |

Computed on the full calendar grid per neighbourhood, for both `weighted_index` and `incident_count`.
Rows whose target or any feature touches 2026-09 are excluded. For the GLM, count-like features enter as `log1p(x)`
(raw counts into a log-link model is what made the first draft score 21 MAE instead of 13).

## 6. Evaluation (same rows for every method)

- Folds, expanding window, split by **target** month: A = test 2025-01..2025-12 (288 points);
  B = test 2026-01..2026-08 (192 points). Train from targets 2010-01 onward.
- Baselines: trailing 3-month mean, trailing 12-month mean, same month last year. The 12-month mean is the bar to
  beat at horizon 2 (it beat the 3-month mean in 19 of 24 areas in our test).
- Regression metrics on the number: MAE, RMSE, WAPE (= sum |error| / sum actual), MAE excluding Central Business
  District (it dominates), and "areas where the method beats the 12-month mean" out of 24.
- Classification metrics on the tier: accuracy, macro-F1 and per-tier recall of the predicted tier against the tier
  computed from the realised value, next to the majority-class accuracy (always guessing the most common realised
  tier), which is the honest baseline. (Recall and F1 apply to the three tiers, not to the number itself.)
- Reference result from 2026-10-03 on `incident_count`, pooled MAE at horizon 2: 3-month mean 14.2, 12-month mean
  13.7, Poisson GLM 13.3, Random Forest 14.8, blend 13.1. Same ranking on the weighted index. Expect the same shape.
  (The final run reproduces these count figures exactly. On the weighted index the ranking differs slightly: GLM
  713.1, blend 716.5, 12-month mean 745.5, Random Forest 775.4, 3-month mean 784.2.)
- Written into `reports/evaluation.md` with the train/test ranges, one table per horizon, and the decision taken;
  the model study and the tier grid are in `reports/model_study.md`.

**Results (final run, 2026-10-04; data through 2026-08, horizon 2, 480 pooled test rows):**

- Shipped model: Poisson GLM (`poisson_glm`). Five alternatives were tested under the pre-registered rule
  (decision 4); none qualified.
- `weighted_index` pooled MAE 713.1 vs 745.5 for the 12-month mean: **4.3% lower**. On fold B alone the 12-month
  mean is better (630.2 vs 673.1). WAPE 12.9%.
- `incident_count` pooled MAE 13.3 vs 13.7 for the 12-month mean.
- 80% range (forecast x 0.658..1.368): fold A ratios applied to fold B covered **79.7%** (out of sample).
- Tiers (decision 5): accuracy **58.9%** vs 42.4% for always guessing the most common tier; macro-F1 0.583. The
  12-month mean gets 59.1%, so the tier's skill comes from the seasonal reference, not from the model.
- October 2026 map: 8 `below_typical`, 8 `typical`, 7 `above_typical`, 1 `insufficient_data` (Musqueam).
- Noise floor: for the median area (Marpole, about 66 reported incidents a month) roughly 12% of a month's count is
  Poisson noise, so more than half of the remaining error is irreducible (54% on the count, 66% on the index, under
  an optimistic Poisson model).
- Every evaluation number the app shows comes from `ml/outputs/meta.json` (section 7).

## 7. Outputs (the contract with backend and frontend)

`ml/outputs/forecast_2026-10.json`, one object per neighbourhood (values illustrative):

```json
{
  "neighbourhood": "West End",
  "month": "2026-10",
  "mode": "forecast",
  "forecast_weighted_index": 2140,
  "forecast_incident_count": 97,
  "interval_low": 1700,
  "interval_high": 2650,
  "relative_activity_tier": "above_typical",
  "pct_vs_typical": 12.4,
  "baseline_weighted_index": 1980,
  "drivers": ["Last 3 months were 11% above this area's 12-month average", "October is typically close to an average month city-wide"],
  "data_through": "2026-08",
  "horizon_months": 2,
  "model": "poisson_glm",
  "typical_weighted_index": 1904
}
```

- `typical_weighted_index` (added 2026-10-04, additive): the tier reference level that `pct_vs_typical` and
  `relative_activity_tier` are measured against, i.e. the same calendar month one year earlier (decision 5).
- `baseline_weighted_index` is still the 12-month mean, the baseline the forecast is compared with.

`ml/outputs/history.json`: per neighbourhood and month, `weighted_index`, `incident_count`, `relative_activity_tier`,
`pct_vs_typical`, `is_partial`. Tiers come from the same `tiers.py` rule as the forecast.

`ml/outputs/meta.json` (added 2026-10-04, written by `forecast.py`): one object describing the run. The app reads
it first; every evaluation figure and label it shows (model name, months, tier wording, range level, the
"How well does it forecast?" block) comes from this file.

| key | meaning (final value) |
|---|---|
| `app` | `"NeighbourCast"` |
| `model` | shipped model id (`"poisson_glm"`) |
| `model_description` | one plain sentence describing the model |
| `data_through` | last complete month (`"2026-08"`) |
| `forecast_month` | `"2026-10"`; also names the forecast file |
| `horizon_months` | `2` |
| `tier_window_months` | `12` |
| `tier_thresholds_pct` | `[-10.0, 10.0]` |
| `tier_reference` | `"seasonal"` (or `"trailing_mean"`) |
| `interval_level` | `0.8` |
| `evaluation` | `folds` (list of `name`, `train_target_months`, `test_target_months`, `n_train`, `n_test`); `pooled_mae_weighted_index` {`mean_12`, `previous_glm`, `shipped`}; `improvement_vs_mean_12_pct`; `improvement_vs_previous_pct`; `wape_pct`; `interval_coverage_pct`; `tier_accuracy_pct`; `tier_majority_baseline_pct`; `tier_macro_f1` |
| `weights_source` | URL of the Statistics Canada weights table |
| `generated_from` | the input csv (`data/processed/neighbourhood_monthly.csv`) |
| `notes` | list of plain-language notes (selection result, pooling, coverage, tier rule, noise floor, weights) |

Backend serves these three files (`/forecast`, `/history`, `/meta`, plus `/health`, `/areas`, `/boundaries`); the
frontend's static copies are refreshed with `npm run sync-data`. Nothing is recomputed at request time.

## 8. Folder structure on `ml-forecast`

```
ml/
  README.md            how to run, in order
  config.py            weights (cited), horizon, split dates, selection rule, tier window / thresholds / reference
                       (single source of truth)
  requirements.txt
  src/
    common.py          repo paths, loads the processed csv, computes weighted_index from the weights
    build_features.py  processed csv -> ml/outputs/features.csv (weighted_index + features, both targets), history.csv
    baselines.py       3-month mean, 12-month mean, same month last year
    train_poisson.py   Poisson GLM on log1p features + month one-hot (C0, shipped) and the extended GLM (C2)
    train_pertype.py   C1: one Poisson GLM per incident type, summed with the severity weights
    train_hgb.py       C3: Poisson gradient boosting with time-ordered early stopping
    train_rf.py        Random Forest on the same rows
    candidates.py      registry of every method, backtest on identical rows, C4 stacking, C5 area correction,
                       the selection rule, final fit
    metrics.py         regression, tier, paired-month and noise-floor metrics
    study.py           model study + tier grid -> reports/model_study.md and the study outputs below
    evaluate.py        folds A/B, all methods, regression + tier metrics, runs study.py
                       -> reports/evaluation.md, evaluation.json
    intervals.py       80% range from pooled backtest ratios
    tiers.py           the one tier rule shared by history, backtest, study and forecast
    forecast.py        final fit on data through 2026-08 -> forecast_2026-10.json/.csv, history.json, meta.json
  outputs/             generated files:
    features.csv, history.csv, history.json
    forecast_2026-10.json, forecast_2026-10.csv
    meta.json                  run summary the app reads (section 7)
    evaluation.json, evaluation_metrics.csv, backtest_predictions.csv
    study_results.csv          every method x target x fold of the model study
    tier_study_results.csv     the 18-cell tier grid
    study_decision.json        the shipped model, the selection table, fold-A choices, noise floor and the tier
                               choice (with its basis, including the fallback)
reports/
  evaluation.md        produced by evaluate.py
  model_study.md       produced by study.py (called by evaluate.py)
```

Retire from the current `ml-forecast`: `data/raw/vpd_incidents.csv`, everything under `data/processed/` that is
not `neighbourhood_monthly.csv`, `scripts/`, `.DS_Store`, the empty root `00-project-debrief.md`.

## 9. Questions we expect an assistant to flag

- Does any code still read the export without 2022, or zero-fill 2022?
- Does any feature use the target month or later, or use 2026-09?
- Are the severity weights cited, and is each VPD `TYPE` mapped to a CSI offence category?
- Is the evaluation split by target month with the baselines on the same rows?
- Do intervals come from backtest ratios, not tree spread?
- Do any field names differ from section 7, or any wording from decision 7?

## 10. Change log

- **2026-10-03:** contract written (decisions 1-7, schema, features, evaluation, outputs, folder structure).
- **2026-10-04:**
  - Decision 2: severity weights set to the official Statistics Canada 85-004-X (2009) Table 1 values and cited,
    with the type-to-offence mapping. The previous working values (29/29/24/60/147/147/66/29) were the same weights
    x ~0.79, so relative weights moved by under 2%; the index scale rose about 27% (pooled GLM MAE 559.9 -> 713.1)
    and the count results are unchanged. The index is described as CSI-inspired, not the official CSI.
  - Decision 4: outcome added. A model study of five candidates was run under a rule fixed beforehand; none
    qualified, so the Poisson GLM ships.
  - Decision 5: tier rule changed from each area's trailing 36-month mean with +-5% bands to a seasonal reference
    (the same calendar month in the last 12 complete months) with +-10% bands, chosen by the grid in
    `reports/model_study.md` with a disclosed fallback. History, backtest and forecast now use one `tiers.py` call
    with one setting (before this, the window had been changed to 12 and only the forecast regenerated, so history
    and forecast disagreed).
  - Section 6: final results added; majority-class accuracy is now the tier baseline.
  - Section 7: `typical_weighted_index` added to the forecast object (additive); `pct_vs_typical` listed in
    `history.json`; new `ml/outputs/meta.json` with its keys.
  - Section 8: `common.py`, `candidates.py`, `study.py`, `metrics.py`, `train_pertype.py`, `train_hgb.py`,
    `meta.json`, `study_results.csv`, `tier_study_results.csv`, `study_decision.json` and `reports/model_study.md` added.
  - `ml/config.py`: `FORECAST_MONTH` typo fixed ("2026-010" -> "2026-10").
