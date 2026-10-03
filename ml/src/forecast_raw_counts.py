"""Forecast next-month reported incident counts by Vancouver neighbourhood.

Expected input columns (case-insensitive):
    neighbourhood, year, month, incident_count

The input may contain several rows per neighbourhood-month (for example one
per incident category). This script sums them into raw monthly counts before
modelling. It forecasts *reported incident counts*, not individual behaviour
or a safety score.

Example:
    python forecast_raw_counts.py \
      --input data/processed/neighbourhood_monthly.csv \
      --output-dir ml/outputs
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


REQUIRED_COLUMNS = {"neighbourhood", "year", "month", "incident_count"}
NUMERIC_FEATURES = ["lag_1", "lag_3_mean", "lag_6_mean", "month_number"]
CATEGORICAL_FEATURES = ["neighbourhood"]


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase/standardize column names and validate the required schema."""
    df = df.copy()
    df.columns = [str(column).strip().lower().replace(" ", "_") for column in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            "Input is missing required columns: " + ", ".join(sorted(missing))
        )
    return df


def parse_month(df: pd.DataFrame) -> pd.DataFrame:
    """Convert numeric or month-name inputs into a monthly timestamp."""
    df = df.copy()
    month_as_number = pd.to_numeric(df["month"], errors="coerce")

    if month_as_number.notna().all():
        df["month_number"] = month_as_number.astype(int)
    else:
        parsed_names = pd.to_datetime(df["month"].astype(str), format="%B", errors="coerce")
        parsed_abbrev = pd.to_datetime(df["month"].astype(str), format="%b", errors="coerce")
        parsed = parsed_names.fillna(parsed_abbrev)
        if parsed.isna().any():
            bad = df.loc[parsed.isna(), "month"].unique()[:5]
            raise ValueError(f"Could not parse month values: {bad}")
        df["month_number"] = parsed.dt.month

    if not df["month_number"].between(1, 12).all():
        raise ValueError("month must be a number from 1 to 12 or a month name")

    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["incident_count"] = pd.to_numeric(df["incident_count"], errors="raise")
    if (df["incident_count"] < 0).any():
        raise ValueError("incident_count cannot be negative")

    df["date"] = pd.to_datetime(
        {"year": df["year"], "month": df["month_number"], "day": 1}
    )
    return df


def build_monthly_panel(raw: pd.DataFrame) -> pd.DataFrame:
    """Sum duplicate rows and insert missing months as zero-count months."""
    grouped = (
        raw.groupby(["neighbourhood", "date"], as_index=False)["incident_count"]
        .sum()
        .sort_values(["neighbourhood", "date"])
    )

    panels = []
    for neighbourhood, part in grouped.groupby("neighbourhood", sort=False):
        dates = pd.date_range(part["date"].min(), part["date"].max(), freq="MS")
        panel = pd.DataFrame({"date": dates})
        panel["neighbourhood"] = neighbourhood
        panel = panel.merge(part, on=["neighbourhood", "date"], how="left")
        panel["incident_count"] = panel["incident_count"].fillna(0.0)
        panels.append(panel)

    monthly = pd.concat(panels, ignore_index=True)
    monthly["year"] = monthly["date"].dt.year
    monthly["month_number"] = monthly["date"].dt.month
    return monthly.sort_values(["neighbourhood", "date"]).reset_index(drop=True)


def add_lag_features(monthly: pd.DataFrame) -> pd.DataFrame:
    """Create only backward-looking features; no future information leaks in."""
    df = monthly.copy().sort_values(["neighbourhood", "date"])
    group = df.groupby("neighbourhood", group_keys=False)["incident_count"]
    df["lag_1"] = group.shift(1)
    df["lag_3_mean"] = group.transform(lambda values: values.shift(1).rolling(3).mean())
    df["lag_6_mean"] = group.transform(lambda values: values.shift(1).rolling(6).mean())
    return df


def make_model() -> Pipeline:
    preprocess = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            ("area", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    # Poisson regression is a simple, interpretable count model.
    return Pipeline(
        steps=[
            ("preprocess", preprocess),
            ("model", PoissonRegressor(alpha=0.5, max_iter=1000)),
        ]
    )


def evaluate(features: pd.DataFrame) -> dict[str, float]:
    """Compare ML with a trailing-three-month baseline on later months."""
    unique_dates = np.sort(features["date"].unique())
    test_months = min(6, max(1, len(unique_dates) // 5))
    test_start = unique_dates[-test_months]
    train = features[features["date"] < test_start].copy()
    test = features[features["date"] >= test_start].copy()

    if train.empty or test.empty:
        raise ValueError("Not enough monthly history for a time-based evaluation")

    model = make_model()
    model.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train["incident_count"])
    ml_prediction = np.clip(
        model.predict(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES]), 0, None
    )
    baseline_prediction = test["lag_3_mean"].to_numpy()

    return {
        "train_end": str(pd.Timestamp(train["date"].max()).date()),
        "test_start": str(pd.Timestamp(test["date"].min()).date()),
        "test_end": str(pd.Timestamp(test["date"].max()).date()),
        "baseline_mae": float(mean_absolute_error(test["incident_count"], baseline_prediction)),
        "model_mae": float(mean_absolute_error(test["incident_count"], ml_prediction)),
        "baseline_rmse": float(mean_squared_error(test["incident_count"], baseline_prediction) ** 0.5),
        "model_rmse": float(mean_squared_error(test["incident_count"], ml_prediction) ** 0.5),
    }


def forecast_next_month(features: pd.DataFrame) -> pd.DataFrame:
    """Fit on all completed months and forecast one month for each neighbourhood."""
    training = features.dropna(subset=NUMERIC_FEATURES).copy()
    model = make_model()
    model.fit(training[NUMERIC_FEATURES + CATEGORICAL_FEATURES], training["incident_count"])

    future_rows = []
    for neighbourhood, part in features.groupby("neighbourhood", sort=False):
        part = part.sort_values("date")
        next_date = part["date"].max() + pd.offsets.MonthBegin(1)
        counts = part["incident_count"].to_numpy(dtype=float)
        future_rows.append(
            {
                "neighbourhood": neighbourhood,
                "date": next_date,
                "year": next_date.year,
                "month": next_date.month,
                "lag_1": counts[-1],
                "lag_3_mean": counts[-3:].mean(),
                "lag_6_mean": counts[-6:].mean() if len(counts) >= 6 else counts.mean(),
                "month_number": next_date.month,
            }
        )

    future = pd.DataFrame(future_rows)
    future["forecast_count"] = np.clip(
        model.predict(future[NUMERIC_FEATURES + CATEGORICAL_FEATURES]), 0, None
    ).round(1)
    return future[["neighbourhood", "date", "year", "month", "forecast_count"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to source CSV")
    parser.add_argument("--output-dir", default="ml/outputs", help="Where to save outputs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = parse_month(normalise_columns(pd.read_csv(args.input)))
    monthly = build_monthly_panel(raw)
    features = add_lag_features(monthly).dropna(subset=NUMERIC_FEATURES).copy()

    metrics = evaluate(features)
    forecast = forecast_next_month(features)

    monthly.to_csv(output_dir / "monthly_raw_counts.csv", index=False)
    forecast.to_csv(output_dir / "next_month_raw_count_forecast.csv", index=False)
    pd.DataFrame([metrics]).to_csv(output_dir / "evaluation_metrics.csv", index=False)

    print("Saved:")
    print(f"  {output_dir / 'monthly_raw_counts.csv'}")
    print(f"  {output_dir / 'next_month_raw_count_forecast.csv'}")
    print(f"  {output_dir / 'evaluation_metrics.csv'}")
    print("\nTime-based evaluation:")
    for name, value in metrics.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
