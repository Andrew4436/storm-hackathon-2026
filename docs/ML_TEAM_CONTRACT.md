# ML team contract: Vancouver neighbourhood incident forecast

Written 2026-10-03 (StormHacks 2026, deadline Sunday 12:00 PM PDT); updated 2026-10-04 to match the final pipeline
(see the change log at the end). This is the single source of truth for the `data-pipeline` and `ml-forecast` branches. It is written for teammates AND for their AI assistants (Cursor, Codex,
Claude Code). If anything you know contradicts this file, say so before writing code; we fix the contract, then the code.

## 1. What we are building

A map of Vancouver's 24 VPD neighbourhoods. Historical mode shows reported-incident activity per neighbourhood per
month. Forecast mode shows a forecast for **October 2026** with an uncertainty range and the chances that the month
ends below, within or above that neighbourhood's usual level (its own history, decision 5). No place is judged or rated (wording rules in decision 7). Unit of everything:
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
5. **Probabilities, not labels** (team decision 2026-10-04; `meta.json` says `"tier_mode": "probabilistic"`).
   - **Reference level and band (unchanged).** Each neighbourhood is compared only with its own **usual level**, a
     **seasonal** reference: the same calendar month within the last `TIER_WINDOW_MONTHS` (12) complete months, i.e.
     the same month one year earlier (`TIER_REFERENCE = "seasonal"`). The band is `TIER_THRESHOLDS_PCT = (-10, +10)`:
     more than 10% below the usual level, within 10% of it, or more than 10% above it. Areas averaging fewer than
     `TIER_MIN_MEAN` (10) incidents a month are `insufficient_data` (Musqueam). One function, `ml/src/tiers.py`,
     applies the reference and band identically to history, backtest and forecast. Each forecast record carries the
     usual level as `typical_weighted_index`.
   - **Output.** For the forecast month, the chance of each of the three outcomes: `p_below`, `p_within`, `p_above`
     (3 decimals, summing to 1.000, `null` for `insufficient_data`), plus `most_likely` (the largest of the three) and
     the same chances for the reported-incident count (`p_*_count`). `ml/src/probabilities.py` combines the point
     forecast F with the ratios actual / forecast of the shipped model's backtest (the same 480 points as the 80%
     range), smoothed by a Gaussian kernel on log-ratios (Scott's-rule bandwidth, 0.107 today): `p_below` is the
     chance that ratio x F falls under usual x 0.90, `p_above` the chance it exceeds usual x 1.10. A lognormal fit is
     the stated alternative and is used only if its out-of-sample Brier score (above + below, both fold directions)
     is at most the kernel's; it was not (0.7060 vs 0.6895).
   - **Why.** The band (+-10%) is narrower than the forecast error (80% range about -34%..+37% around the forecast),
     so in the October forecast the chance of landing within it is at most 31%. A hard label would have
     called no October area `typical` and stated every call with false certainty; chances carry both the direction
     and the uncertainty.
   - **Map.** No labels on screen. In forecast mode the map colours continuously by `p_above - p_below` (teal where
     below is more likely, grey even odds, amber where above is more likely); in historical mode by the realised
     `pct_vs_typical`, full colour at 30% either way. The drawer shows the three chances as a bar and one sentence.
   - **Label kept only for compatibility.** `relative_activity_tier` (`below_typical` / `typical` / `above_typical`
     / `insufficient_data`) stays in both files: in the forecast it equals `most_likely`; in `history.json` it is the
     realised outcome against the same band. The app reads it only to spot `insufficient_data`.
   - **How the reference and band were chosen.** By the pre-registered grid search in `reports/model_study.md` ("Tier
     decision"): window {12, 24, 36} months x thresholds {+-5, +-8, +-10}% x reference {trailing mean, seasonal};
     highest skill (macro-F1 minus the accuracy of always guessing the most common tier), subject to (a) at least 3
     areas below and 3 above in the 2026-10 forecast and (b) 30-60% of history months `typical`. **Fallback,
     disclosed:** no cell met both constraints, so a fallback added after seeing the grid keeps (a), drops (b) and
     takes the highest skill; the pick has 25% `typical` history months. Without either constraint the same cell has
     the highest skill in the grid. Every trailing-mean setting, including the 2026-10-03 rule (36 months, +-5%), had
     negative skill. A single-month reference is noisy, so part of the skill is regression to the mean.
6. **Uncertainty:** an 80% range from backtest error ratios (actual / forecast) pooled across neighbourhoods.
   Not from Random Forest tree spread (it covered 66% at a nominal 80% in our test and depends on `min_samples_leaf`).
7. **Wording:** "reported incidents", "severity-weighted activity", "relative to this area's own history",
   "uncertainty range", "chance of ending above / below its usual level". Never "crime risk", "safety score", "safe",
   "unsafe", "dangerous", "predict crime". `below_typical` / `typical` / `above_typical` are field values, never
   labels shown to users.

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
- Proper scores on the probabilities (decision 5), out of sample: the ratios that build the chances come from one
  test year and the chances are scored on the other (2025 -> 2026 is the headline, 184 area-months; 2026 -> 2025 is
  reported too); `insufficient_data` is left out. Brier score for "above" and for "below" (mean squared gap between
  the chance given and what happened), and the ranked probability score (RPS) over the three ordered outcomes, so
  calling "below" when "above" happened costs more than calling "within". Lower is better. Baselines: the base rates
  of the ratio year given to every area, and a hard label (100% on the most likely outcome). Reliability tables group
  area-months by the chance given (20% bins) and show how often the event happened.
- Most-likely label, for reference: accuracy, macro-F1 and per-outcome recall of the label from the point forecast
  against the outcome computed from the realised value, next to the majority-class accuracy (always guessing the most
  common realised outcome), which is the honest baseline. These are no longer what the app shows.
- Reference result from 2026-10-03 on `incident_count`, pooled MAE at horizon 2: 3-month mean 14.2, 12-month mean
  13.7, Poisson GLM 13.3, Random Forest 14.8, blend 13.1. Same ranking on the weighted index. Expect the same shape.
  (The final run reproduces these count figures exactly. On the weighted index the ranking differs slightly: GLM
  713.1, blend 716.5, 12-month mean 745.5, Random Forest 775.4, 3-month mean 784.2.)
- Written into `reports/evaluation.md` with the train/test ranges, one table per horizon, the decision taken and the
  probability scores and reliability tables ("Probabilities instead of tiers"); the model study and the tier grid are
  in `reports/model_study.md`.

**Results (final run, 2026-10-04; data through 2026-08, horizon 2, 480 pooled test rows):**

- Shipped model: Poisson GLM (`poisson_glm`). Five alternatives were tested under the pre-registered rule
  (decision 4); none qualified.
- `weighted_index` pooled MAE 713.1 vs 745.5 for the 12-month mean: **4.3% lower**. On fold B alone the 12-month
  mean is better (630.2 vs 673.1). WAPE 12.9%.
- `incident_count` pooled MAE 13.3 vs 13.7 for the 12-month mean.
- 80% range (forecast x 0.658..1.368): fold A ratios applied to fold B covered **79.7%** (out of sample).
- Probabilities (decision 5; Gaussian kernel on log-ratios, 480 pooled backtest ratios, bandwidth 0.107), ratios from
  2025 scored on 2026 (184 area-months): Brier "above" **0.160** vs 0.239 for the base rate, Brier "below" **0.186**
  vs 0.242; RPS **0.173** vs 0.241 for the base rate (28% better) and 0.264 for a hard label.
- Reliability (same rows): when the chance of "above" was 80-100% it happened 90% of the time (21 area-months);
  60-80%, 75% (20); 40-60%, 50% (34). Weak spots: "above" at 20-40% said 30% and happened 17% (58), and the small
  "below" 80-100% bin said 88% and happened 71% (14).
- Most-likely label, for reference (decision 5): the old point-forecast label was right **58.9%** of the time vs 42.4%
  for always guessing the most common outcome; macro-F1 0.583. The 12-month mean gets 59.1%, so that skill comes from
  the seasonal reference, not from the model.
- October 2026 forecast: no area has "within" as its most likely outcome (the band is narrower than the forecast
  error); `most_likely` is `below_typical` for 14 areas, `above_typical` for 9, `insufficient_data` for 1 (Musqueam).
  The map shows the chances, not these values.
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
  "typical_weighted_index": 1904,
  "p_below": 0.215,
  "p_within": 0.262,
  "p_above": 0.523,
  "most_likely": "above_typical",
  "p_below_count": 0.198,
  "p_within_count": 0.255,
  "p_above_count": 0.547
}
```

- `typical_weighted_index` (added 2026-10-04, additive): the usual level that `pct_vs_typical` and the chances are
  measured against, i.e. the same calendar month one year earlier (decision 5).
- `p_below`, `p_within`, `p_above` (added 2026-10-04, additive): the chance that the month's `weighted_index` ends more
  than 10% below, within 10% of, or more than 10% above `typical_weighted_index` (decision 5). Floats with 3
  decimals summing to 1.000; `null` for `insufficient_data`. These drive the map colour (`p_above - p_below`).
- `most_likely` (added 2026-10-04): the largest of the three, as `below_typical` / `typical` / `above_typical`
  (`insufficient_data` for Musqueam). `relative_activity_tier` now equals it and is kept only for compatibility.
- `p_below_count`, `p_within_count`, `p_above_count` (added 2026-10-04): the same chances for `incident_count`,
  built from the count backtest. Not shown by the app today.
- `pct_vs_typical` is the point forecast's deviation from the usual level; the app uses it only when a forecast file
  has no chances (an older pipeline).
- `baseline_weighted_index` is still the 12-month mean, the baseline the forecast is compared with.

`ml/outputs/history.json`: per neighbourhood and month, `weighted_index`, `incident_count`, `relative_activity_tier`,
`pct_vs_typical`, `is_partial`. `pct_vs_typical` (realised deviation from the usual level, `null` before 12 months of
history) colours past months; `relative_activity_tier` comes from the same `tiers.py` reference and band and is read
only to spot `insufficient_data`. History carries no probabilities: past months are known.

`ml/outputs/meta.json` (added 2026-10-04, written by `forecast.py`): one object describing the run. The app reads
it first; every evaluation figure and piece of wording it builds from the pipeline (model name, months, the usual
level and its band, range level, the "How well does it forecast?" block including the probability scores) comes from
this file.

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
| `tier_mode` | `"probabilistic"`: forecast records carry `p_below` / `p_within` / `p_above` (decision 5) |
| `probability_method` | one plain sentence on how the chances are built (today: Gaussian kernel on the log-ratios of 480 backtest ratios, Scott's-rule bandwidth 0.107). The short id of the chosen smoothing (`"kde"` or `"lognormal"`) is `probabilistic.method` in `ml/outputs/evaluation.json` |
| `interval_level` | `0.8` |
| `evaluation` | `folds` (list of `name`, `train_target_months`, `test_target_months`, `n_train`, `n_test`); `pooled_mae_weighted_index` {`mean_12`, `previous_glm`, `shipped`}; `improvement_vs_mean_12_pct`; `improvement_vs_previous_pct`; `wape_pct`; `interval_coverage_pct`; `tier_accuracy_pct`, `tier_majority_baseline_pct`, `tier_macro_f1` (most-likely label, for reference); `probabilistic` (below) |
| `evaluation.probabilistic` | out-of-sample scores of the chances (ratios from 2025 scored on 2026): `brier_above` (0.1595), `brier_below` (0.1864), `brier_above_baseline` (0.2394), `brier_below_baseline` (0.2417), `rps` (0.173), `rps_baseline` (0.2406), `rps_hard_tier` (0.2636); `reliability_above`, `reliability_below` (lists of {`bin`, `predicted`, `observed`, `n`} over five 20% bins); `statement` (the plain-language calibration sentence the app shows as written); `scored_on` (`"ratios from 2025 applied to 2026 (184 rows)"`) |
| `weights_source` | URL of the Statistics Canada weights table |
| `generated_from` | the input csv (`data/processed/neighbourhood_monthly.csv`) |
| `notes` | list of plain-language notes (selection result, pooling, coverage, reference and band, noise floor, probability fields and scoring, most-likely counts, weights) |

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
    tiers.py           the one reference level and band shared by history, backtest, study and forecast
    probabilities.py   p_below / p_within / p_above from the point forecast and smoothed backtest ratios, and
                       their out-of-sample scores (Brier, RPS, reliability)
    forecast.py        final fit on data through 2026-08 -> forecast_2026-10.json/.csv, history.json, meta.json
  outputs/             generated files:
    features.csv, history.csv, history.json
    forecast_2026-10.json, forecast_2026-10.csv
    meta.json                  run summary the app reads (section 7)
    evaluation.json, evaluation_metrics.csv, backtest_predictions.csv
    probability_reliability.csv  every reliability row (target x fold direction x event x bin)
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
- **2026-10-04 (probabilities):**
  - Decision 5: "Tiers" becomes "Probabilities, not labels". The usual level (same calendar month one year earlier)
    and the +-10% band are unchanged; the forecast now gives `p_below` / `p_within` / `p_above` and `most_likely`
    from a Gaussian kernel on the log of 480 backtest ratios (bandwidth 0.107). Reason: the band is narrower than the
    forecast error (80% range about -34%..+37%), so a hard label would have called no October area `typical`. The map
    colours continuously (`p_above - p_below` for the forecast, realised `pct_vs_typical` saturating at 30% for past
    months) and shows no labels; `relative_activity_tier` = `most_likely`, kept only for compatibility.
  - Decision 7: "chance of ending above / below its usual level" added; tier names are field values, not on-screen
    labels.
  - Section 6: proper-score evaluation added (Brier above / below, RPS, reliability, out of sample, against base rates
    and a hard label) with its results; the old tier metrics stay as "most-likely label, for reference".
  - Section 7: forecast fields `p_below`, `p_within`, `p_above`, `most_likely`, `p_*_count` (additive); meta keys
    `tier_mode`, `probability_method`, `evaluation.probabilistic` (scores, reliability bins, `statement`,
    `scored_on`).
  - Section 8: `probabilities.py` and `probability_reliability.csv` added.
  - Unchanged: model, MAE (713.1 vs 745.5), WAPE 12.9%, 80% range coverage 79.7%, severity weights.
