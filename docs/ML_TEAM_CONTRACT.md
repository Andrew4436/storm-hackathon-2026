# ML team contract: Vancouver neighbourhood incident forecast

Written 2026-10-03 (StormHacks 2026, deadline Sunday 12:00 PM PDT). This is the single source of truth for the
`data-pipeline` and `ml-forecast` branches. It is written for teammates AND for their AI assistants (Cursor, Codex,
Claude Code). If anything you know contradicts this file, say so before writing code; we fix the contract, then the code.

## 1. What we are building

A map of Vancouver's 24 VPD neighbourhoods. Historical mode shows reported-incident activity per neighbourhood per
month. Forecast mode shows a forecast for **October 2026** with an uncertainty range and a tier relative to that
neighbourhood's own recent history. Nothing is labelled safe, unsafe, dangerous or good. Unit of everything:
**one neighbourhood x one calendar month**.

## 2. Decisions (firm unless the team changes this file)

1. **Data file:** `data/processed/neighbourhood_monthly.csv` on `main`, produced by `data/stormhacks2026_data_cleaning.ipynb`.
   Nobody re-cleans raw data in `ml/`. The old `data/raw/vpd_incidents.csv` and `scripts/weighted_index_dataset.py`
   on `ml-forecast` are retired (they used the export that is missing 2022).
2. **Target:** `weighted_index` = sum over the 8 included types of (monthly count x severity weight).
   The weights follow the Statistics Canada Crime Severity Index approach (per-offence weights derived from
   incarceration rates and sentence lengths). Working values are in `ml/config.py`; the StatCan table used and the
   mapping from each VPD `TYPE` to a CSI offence category must be cited there before the demo.
   `incident_count` (unweighted) is forecast by the same code as a secondary output, because judges and users
   understand "about 95 reported incidents" more easily than an index value.
3. **Horizon:** forecast month 2026-10 from data through **2026-08** (horizon = 2). 2026-09 is partial and is never a
   feature source, a training target, or "the latest month".
4. **Models:** Poisson GLM and Random Forest, both implemented, both evaluated on identical rows against three
   baselines. The shipped model is whichever has the lower pooled MAE on `weighted_index`; this rule is fixed now,
   before the final run. A 50/50 blend of the GLM and the 12-month mean is also reported.
5. **Tiers:** `below_typical` / `typical` / `above_typical`, computed per neighbourhood against its own trailing
   `TIER_WINDOW_MONTHS` (36) complete months. Same rule in historical and forecast mode. Thresholds live in config
   and are tuned once at the 7 PM checkpoint so the map is not one colour.
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
  computed from the realised value. (Recall and F1 apply to the three tiers, not to the number itself.)
- Reference result from 2026-10-03 on `incident_count`, pooled MAE at horizon 2: 3-month mean 14.2, 12-month mean
  13.7, Poisson GLM 13.3, Random Forest 14.8, blend 13.1. Same ranking on the weighted index. Expect the same shape.
- Written into `reports/evaluation.md` with the train/test ranges, one table per horizon, and the decision taken.

## 7. Outputs (the contract with backend and frontend)

`ml/outputs/forecast_2026-10.json`, one object per neighbourhood:

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
  "model": "poisson_glm"
}
```

`ml/outputs/history.json`: per neighbourhood and month, `weighted_index`, `incident_count`, `relative_activity_tier`,
`is_partial`. Backend serves these two files; nothing is recomputed at request time.

## 8. Folder structure on `ml-forecast`

```
ml/
  README.md            how to run, in order
  config.py            weights, horizon, split dates, tier window and thresholds  (single source of truth)
  requirements.txt
  src/
    build_features.py  processed csv -> ml/outputs/features.csv (weighted_index + features, both targets)
    baselines.py       3-month mean, 12-month mean, same month last year
    train_poisson.py   Poisson GLM on log1p features + month one-hot
    train_rf.py        Random Forest on the same rows
    evaluate.py        folds A/B, all methods, regression + tier metrics -> reports/evaluation.md, evaluation.json
    intervals.py       80% range from pooled backtest ratios
    tiers.py           tier rule shared by history and forecast
    forecast.py        final fit on data through 2026-08 -> ml/outputs/forecast_2026-10.json, history.json
  outputs/             generated files (features.csv, forecast json, history json)
reports/
  evaluation.md        produced by evaluate.py
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
