# Guide: `ml-forecast` Branch

## Your mission

Build a simple, evaluated one-month area-level forecast from the prepared monthly dataset. Your job is credibility, not model complexity.

You own `ml/` and `reports/`. Do not edit data-cleaning scripts or frontend/backend code.

## Before coding

1. Read `00-project-brief.md`.
2. Confirm the input schema with the data owner.
3. Agree that the target is **next month’s reported-incident count per neighbourhood**.
4. Agree on risk tiers and the model output schema with the backend owner.

## Step-by-step work

### 1. Establish the baseline first

Implement a baseline forecast, such as:

- previous month’s count;
- trailing 3-month average; or
- same month in prior year, if enough history exists.

Save baseline predictions. This is your fallback if the ML model adds no meaningful value.

### 2. Make a proper time split

- Train only on earlier months.
- Hold out the latest available months for testing.
- Never randomly shuffle time-series data.
- Record training range and testing range in `reports/evaluation.md`.

### 3. Build one modest model

Use an interpretable model appropriate for count/trend data, such as regularized regression, random forest/gradient boosting with constrained features, or a simple count model.

For now, we will start with a simple regression model.

Start with lags, rolling averages, season/month, and area identity. Do not add weather/transit features until the core model and integration work.

### 4. Evaluate honestly

- Compare against the baseline using MAE (and optionally RMSE).
- Report the result across the held-out months.
- If the model is worse than baseline, use the baseline in the MVP and say so internally. A reliable baseline is valid.
- Do not claim causal explanations or certainty.

### 5. Convert output for the product

For each neighbourhood, create a forecast export including:

```text
area,month,forecast_count,risk_tier,confidence,drivers
```

Risk tiers must be relative to historical values for that area. Confidence may be a simple calibrated label based on data availability/forecast variation; document how it is computed.

Drivers should be factual, templated statements derived from model features, e.g. `Recent 3-month trend above area baseline`. Do not fabricate explanations.

### 6. Hand off

- Export a stable CSV or JSON to the agreed location/schema.
- Give backend owner 2–3 representative output rows.
- Supply one short accuracy result and one limitations statement for the frontend/pitch.

## Push checkpoints

1. **Early push:** baseline and time-split skeleton.
2. **Checkpoint 1:** evaluation of baseline plus a saved predictions file.
3. **Checkpoint 2:** model comparison, forecast export, and `reports/evaluation.md`.

## Definition of done

- Forecast runs from a documented command/script.
- Test performance is reported against the baseline.
- Output matches the agreed API data contract.
- Limitations are plain language and ready for the UI.
