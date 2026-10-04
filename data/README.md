# data/: VPD reported-incident data, cleaned to neighbourhood x month

This folder holds the raw Vancouver Police Department (VPD) open data, the notebook that cleans it, and the one table everyone else consumes.
**ML, backend and frontend: use `processed/neighbourhood_monthly.csv`** (24 neighbourhoods x 285 months, 2003-01 to 2026-09, one row per neighbourhood-month).
Use `raw/vancouver_crime_data.csv` only if you need to re-run or audit the cleaning in `stormhacks2026_data_cleaning.ipynb`. Owner: `data-pipeline` branch.

## For AI assistants: invariants

These are rules, not suggestions. They apply to any code that reads the raw or processed files.

- **Never call `drop_duplicates` (or any de-duplication) on the raw incidents.** About 42% of "Offence Against a Person" rows are exact copies of another row by design. VPD blanks their time (`HOUR=MINUTE=0`), block (`OFFSET TO PROTECT PRIVACY`) and coordinates (`X=Y=0`). They are separate incidents.
- **Never derive or correct `NEIGHBOURHOOD` from `X`/`Y`.** `NEIGHBOURHOOD` is the only location field used. `X`/`Y` are UTM zone 10N metres. All violent offences are at 0,0, 31 rows have no coordinates (all of them collisions with a blank neighbourhood, dropped in step 1), and 4 are far outside Vancouver.
- **Never use `HUNDRED_BLOCK`, `X`, `Y`, `DAY`, `HOUR` or `MINUTE` in the product.** The unit is neighbourhood x month only. The brief forbids address-level or street-level scoring.
- **Never treat 2026-09 as a complete month.** It has `is_partial = 1` (data ends 2026-09-25, about 70% of a normal month). Do not use it as a training target, an evaluation point, or "the latest month". **The last complete month is 2026-08.**
- **Never forecast, map or display Homicide or Vehicle Collision types.** They were removed on purpose (see Cleaning steps). Do not add them back.
- **Never merge Musqueam into Dunbar-Southlands**, and never drop Stanley Park or Musqueam from the data.
- **Zeros in `incident_count` are true zeros** only because every month 2003-01..2026-09 was published. If a future extract is missing a month, leave that month empty or NaN, not 0.
- **Do not edit files in `raw/`.** Regenerate `processed/` by re-running the notebook. Never hand-edit it.
- **Wording:** say "reported incidents" and "relative activity". Never write "crime risk", "safety score", "dangerous", "safe" or "predict crime" in UI text, API fields shown to users, or the pitch.

## Files

| Path (relative to `data/`) | Size | Rows | Purpose |
|---|---|---|---|
| `stormhacks2026_data_cleaning.ipynb` | ~0.3 MB | 10 code cells | The cleaning pipeline. Run All from `data/` to regenerate the output. Every step has a markdown note. |
| `raw/vancouver_crime_data.csv` | 87.8 MB | 962,117 | **Canonical raw input.** The VPD all-years export plus the 2022 download, with one header. |
| `processed/neighbourhood_monthly.csv` | 0.24 MB | 6,840 | **The output.** Reported incidents per neighbourhood per month. Written by the notebook's last cell. |
| `README.md` | | | This file. |

Outside this folder:
- `../crimedata_csv_AllNeighbourhoods_AllYears.csv` (85.7 MB, 927,794 rows) is the original export committed at the repo root. **It is missing all of 2022. It is superseded by `raw/vancouver_crime_data.csv`. Do not use it.**
- `../legal_disclaimer.txt` is VPD's legal disclaimer for this data.

## Provenance

- **Source:** VPD GeoDASH open data, https://geodash.vpd.ca/opendata/ (CSV download, all neighbourhoods).
- **Downloaded:** 2026-10-03, as two files:
  1. "AllNeighbourhoods_AllYears": 927,794 rows. VPD's all-years export **does not contain 2022**.
  2. A separate single-year 2022 download: 34,323 rows. (Not kept in the repo; its rows are in `raw/vancouver_crime_data.csv`.)
- **Merge:** the two files were concatenated, keeping a single header row. Result: 927,794 + 34,323 = 962,117 data rows in `raw/vancouver_crime_data.csv`. No other change was made to the raw rows.
- **Coverage:** 2003-01-01 to **2026-09-25** (last incident in the file).
- **Raw columns:** `TYPE, YEAR, MONTH, DAY, HOUR, MINUTE, HUNDRED_BLOCK, NEIGHBOURHOOD, X, Y`.
- **Licence / disclaimer:** see `../legal_disclaimer.txt`. VPD cautions users not to rely on the data to make decisions about the safety of a specific location or area.
- This project is **not affiliated with or endorsed by the Vancouver Police Department**.

## Cleaning steps (in notebook order)

| # | Step | Rows after | Why |
|---|---|---|---|
| 0 | Load `raw/vancouver_crime_data.csv` | 962,117 | Single combined raw file. |
| 1 | Drop rows with blank `NEIGHBOURHOOD` (106 dropped) | 962,011 | Almost all are privacy-offset violent offences and collisions (105 of 106) never assigned to an area. They cannot be mapped. |
| 2 | Add `MONTH_STR = YYYY-MM` | 962,011 | This is the team's month key. It sorts correctly as text. |
| 3 | Chart: incidents by type (11 types) | n/a | Exploration only. |
| 4 | Chart: vehicle collisions per year | n/a | Shows the 2014 break: about 160-350 per year in 2003-2013 (337 in 2013), then 1,568 in 2014 and roughly 850-1,700 per year since (about 1,000-1,200 in recent years). VPD changed how it recorded collisions, so the jump is not a real trend. |
| 5 | Drop 3 types (19,554 dropped): `Vehicle Collision or Pedestrian Struck (with Injury)`, `Vehicle Collision or Pedestrian Struck (with Fatality)`, `Homicide` | 942,457 | Collisions are traffic events and have the 2014 break. Homicide is about 1/month city-wide and must never be forecast or mapped. |
| 6 | Chart: the 8 kept types | n/a | Check the filter. |
| 7 | Chart: monthly totals per year, partial month hatched | n/a | Check that every month exists, including 2022, and see the partial 2026-09. |
| 8 | Group by neighbourhood x month (overall and one column per type), then reindex to the full 24 x 285 grid with `fill_value=0` | 6,840 cells | One row per neighbourhood-month. 18 zero cells were filled in, all in Musqueam. |
| 9 | Export with `is_partial`; asserts: `sum(incident_count) == len(cleaned rows)` (942,457 for this extract), the eight type columns sum to `incident_count` on every row, and each type column matches the raw rows | 6,840 | The output adds up exactly to the cleaned rows, overall and per type. |

The 8 types kept, all summed into `incident_count`: Other Theft 260,241; Theft from Vehicle 260,006; Mischief 122,938; Offence Against a Person 86,552; Break and Enter Residential/Other 75,102; Break and Enter Commercial 51,542; Theft of Vehicle 46,439; Theft of Bicycle 39,637. Total: 942,457.

Deliberately **not** done: no de-duplication, no geocoding or reverse geocoding, no use of block or coordinates, no outlier removal.

## Output schema: `processed/neighbourhood_monthly.csv`

One row per (neighbourhood, month), 14 columns. There are no missing values. Rows are sorted by `neighbourhood`, then `month_str`.

| Column | Type | Meaning | Allowed values |
|---|---|---|---|
| `year` | int | Calendar year | 2003 to 2026 |
| `month` | int | Calendar month | 1 to 12 (not zero-padded) |
| `month_str` | string | Month key, `YYYY-MM` | `2003-01` to `2026-09` (285 values, none missing) |
| `neighbourhood` | string | VPD neighbourhood name, exactly as VPD spells it | the 24 names below |
| `incident_count` | int | Number of reported incidents of the 8 kept types in that neighbourhood and month | >= 0. 0 occurs only for Musqueam (18 cells). |
| `other_theft`, `theft_from_vehicle`, `mischief`, `offence_against_a_person`, `break_and_enter_residential_other`, `break_and_enter_commercial`, `theft_of_vehicle`, `theft_of_bicycle` | int | Reported incidents of that one type in that neighbourhood and month | >= 0. The eight columns sum to `incident_count` on every row. |
| `is_partial` | int (0/1) | 1 if the month is incomplete in the source data | 1 only for `month_str == "2026-09"` (24 rows). Otherwise 0. |

Note: `month` here is the calendar month number (1-12). The team-wide `YYYY-MM` month key (called `month` in the API and forecast export) is `month_str`.

A severity-weighted index is deliberately **not** stored in this file. Compute it as the sum of each type column times its weight; the weights live in `ml/config.py` (`SEVERITY_WEIGHTS`, keyed by these column names) and are owned by the ML branch, so this data file never has to change when weights do.

**The 24 neighbourhoods:** Arbutus Ridge, Central Business District, Dunbar-Southlands, Fairview, Grandview-Woodland, Hastings-Sunrise, Kensington-Cedar Cottage, Kerrisdale, Killarney, Kitsilano, Marpole, Mount Pleasant, Musqueam, Oakridge, Renfrew-Collingwood, Riley Park, Shaughnessy, South Cambie, Stanley Park, Strathcona, Sunset, Victoria-Fraserview, West End, West Point Grey.

**`is_partial` rule:** it flags the latest month in the file, because the extract stops part-way through it (2026-09-25). Filter it out for training, evaluation and "current month" displays. If you show it at all, label it as incomplete.

```python
import pandas as pd
# run from the repo root; from ml/ or backend/ use "../data/processed/neighbourhood_monthly.csv"
df = pd.read_csv("data/processed/neighbourhood_monthly.csv", dtype={"month_str": str})
complete = df[df["is_partial"] == 0]   # 2003-01 .. 2026-08, 6,816 rows
```

## Known data traps

- **Duplicates are real incidents.** About 42% of "Offence Against a Person" rows exactly match another row, because VPD redacts time, block and coordinates for privacy. De-duplicating would silently delete real incidents and break the `942,457` total.
- **Partial final month.** 2026-09 has about 70% of a normal month's rows, and the last days are nearly empty. It will look like a sudden drop if you plot it unflagged.
- **Musqueam is tiny.** It averages about 2-3 incidents/month since 2016 (3.6/month over 2003-2026; computed by the data owner from the processed file). It has all 18 zero months. Forecasts and tiers for it are noise. Show it as "insufficient data".
- **Redacted violent offences.** "Offence Against a Person" has `HOUR=MINUTE=0`, `HUNDRED_BLOCK = "OFFSET TO PROTECT PRIVACY"` and `X=Y=0`. Its neighbourhood is still given and is what we count. Recent months may be under-reported because of reporting lag.
- **The 2014 collision break.** This is why collisions are excluded. Do not re-add them for "more data".
- **X/Y outliers.** 31 rows have no coordinates (all of them collisions with a blank neighbourhood, dropped in step 1), 4 are far outside Vancouver, and all violent offences are at 0,0. This is one reason X/Y is never used.
- **Category mix shifts.** Theft from Vehicle has fallen by about two-thirds since 2003, while Other Theft has risen sharply since 2021. The total can move because of how incidents are classified, not only because of activity.
- **COVID.** There is a visible dip in 2020-21.
- **The root CSV.** `../crimedata_csv_AllNeighbourhoods_AllYears.csv` has no 2022. Using it would create 12 months of fake zeros.

## Map join notes (frontend owner)

The City of Vancouver open dataset "local-area-boundary" has **22 polygons**. The VPD data has **24 neighbourhoods**. Join on name with these exceptions:

| VPD `neighbourhood` | CoV local-area polygon | How to handle |
|---|---|---|
| Central Business District | Downtown | Rename when joining. Same area. |
| Stanley Park | (no polygon) | Draw as a point marker or a custom shape. Do not drop it. |
| Musqueam | Lies inside "Dunbar-Southlands" | Keep it separate. **Never merge it into Dunbar-Southlands.** Show as a marker labelled "insufficient data". |
| The other 21 names | Same name | They match exactly. |

## Modelling notes (already agreed; for context)

- **Target:** `incident_count` for one neighbourhood in one month (8 types summed).
- **Forecast month:** October 2026, a **2-month horizon** from data through 2026-08 (2026-09 is partial and is not used).
- **Evaluation split:** hold out 2026-01..2026-08 as the test period (8 months x 24 neighbourhoods = 192 points). Train on earlier months only.
- **Baselines to beat:** the trailing-12-month mean, and the same month last year.
- **Final model:** retrain on everything through 2026-08, then forecast 2026-10.
- **Tiers** are relative to each neighbourhood's own history, not a citywide or universal scale.
- **Wording rule (team brief):** say "reported incidents" and "relative activity". Never use "crime risk", "safety score", "dangerous", "safe" or "predict crime".

## Limitations text (reuse verbatim)

> This map shows counts of reported, founded incidents from the Vancouver Police Department's open data, grouped by neighbourhood and month; it is not a rating of any place or the people in it, and VPD advises against using this data to judge the safety of a specific location. Counts depend on what is reported and how it is recorded: some incidents are never reported, recent months can be revised as reports arrive late, and the location and time of offences against a person are withheld for privacy. Category definitions and recording practices change over time, and the 2020-21 pandemic period is unusual, so year-to-year comparisons should be read with care. Forecasts show relative activity compared with each neighbourhood's own history, with uncertainty, and very small areas such as Musqueam have too few incidents to forecast meaningfully. These figures are not comparable to Statistics Canada crime statistics, and this project is not affiliated with the Vancouver Police Department.

## How to regenerate

1. Open `data/stormhacks2026_data_cleaning.ipynb` in Jupyter or VS Code. **The working directory must be `data/`**, because paths are relative (`raw/...`, `processed/...`).
2. Run All. It takes about 1 minute.
3. Dependencies: Python 3 with `pandas`, `numpy`, `matplotlib` and a Jupyter kernel (Jupyter, or VS Code with the Jupyter extension, plus `ipykernel`). Developed on Python 3.13 with pandas 3.0.2. Headless: `python -m jupyter nbconvert --to notebook --execute --inplace stormhacks2026_data_cleaning.ipynb`, run from `data/`.
4. Output: `data/processed/neighbourhood_monthly.csv`. It is overwritten each run, and the last cell asserts the total equals the cleaned row count (942,457 for this extract).
5. If a newer VPD extract is used, re-check the expected numbers in this README and in the notebook notes (row counts, last incident date, which month is partial), and confirm that no month is missing before trusting zero-fill.
