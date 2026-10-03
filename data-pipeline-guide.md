# Guide: `data-pipeline` Branch

## Your mission

Turn raw VPD GeoDASH incident data into one trustworthy, documented monthly neighbourhood dataset that the model and backend can use without manual cleanup.

You own `data/raw`, `data/processed`, and `data/README.md`. Do not build the frontend or modify the model code.

## Before coding

1. Read `00-project-brief.md`.
2. Confirm the selected incident categories and neighbourhood naming convention with the team.
3. Confirm that the prediction unit is **one neighbourhood in one calendar month**.
4. Tell the backend and ML owners the exact output column names before they begin integration.

## Step-by-step work

### 1. Acquire the data

- Download the agreed VPD GeoDASH data subset.
- Record the retrieval date, source URL, years included, and any download restrictions in `data/README.md`.
- Keep raw downloads unchanged in `data/raw/`. Never overwrite them with cleaned data.

### 2. Inspect and clean

- Inspect columns, date ranges, categories, duplicate records, missing neighbourhoods, and invalid dates.
- Parse event dates into a standard date type.
- Create `month` in `YYYY-MM` format.
- Use only area-level fields supplied/approved for the project. Never attempt to recover exact addresses or identities.
- Write a repeatable cleaning script; do not rely on manual spreadsheet edits.

### 3. Aggregate

Produce `data/processed/neighbourhood_monthly.csv` with at least:

```text
neighbourhood,month,incident_count
```

Add category columns only if the team has agreed to use them. There must be one row per neighbourhood-month, including zero-count months where feasible.

### 4. Create feature-ready output

Produce `data/processed/model_input.csv` with base fields needed by ML:

```text
neighbourhood,month,incident_count,lag_1,lag_3_mean,lag_6_mean,month_number
```

Do not calculate the future target in a way that leaks information from later months. Clearly document every feature.

### 5. Validate

- Check that each neighbourhood has an expected, continuous monthly time series.
- Spot-check 3–5 rows against raw counts.
- Print row count, date range, neighbourhood count, and missing-value count.
- Send the ML owner a small sample and schema before handing over the full dataset.

## Push checkpoints

1. **Early push:** folder structure, data README, and retrieval instructions.
2. **Checkpoint 1:** reproducible cleaned/aggregated dataset plus schema.
3. **Checkpoint 2:** model-ready dataset and validation summary.

Each push should include a short commit message such as `Add reproducible monthly neighbourhood aggregation`.

## Definition of done

- Another teammate can run your documented script and regenerate the processed files.
- ML can load `model_input.csv` with no cleanup.
- Backend can load a historical monthly dataset with consistent names.
- Data provenance and limitations are written down.

