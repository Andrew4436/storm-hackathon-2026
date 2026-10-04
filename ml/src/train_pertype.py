"""Candidate C1: one Poisson GLM per reported-incident type, summed.

For each of the 8 types in config.TYPE_COLUMNS, a Poisson GLM (log link, config.GLM_PARAMS) is fitted on:
  * log1p of that type's own last_value, mean_3, mean_6, mean_12, same_month_last_year in the area
  * log1p of the area's total incident_count mean_12 (scale: helps small types in big areas)
  * one-hot target_month_number (each type has its own seasonality)
The 8 type forecasts are then combined: weighted_index = sum(weight_k x forecast_k) with config.SEVERITY_WEIGHTS,
incident_count = sum(forecast_k). One fit serves both targets, so `prefix` only selects the combination.

Interface shared with the other model modules:
    model = fit(train_df, prefix)
    yhat  = predict(model, df, prefix)
    per_type(model, df) -> DataFrame of the 8 type forecasts
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

import common  # noqa: F401  (sets up sys.path for config)
import config
from build_features import TYPE_FEATURES

MONTHS = list(range(1, 13))


@dataclass
class PerTypeModel:
    glms: dict[str, PoissonRegressor]
    n_columns: int


def design_matrix(df: pd.DataFrame, t: str) -> np.ndarray:
    cols = [np.log1p(df[f"{t}_{f}"].to_numpy(dtype=float)) for f in TYPE_FEATURES]
    cols.append(np.log1p(df["ic_mean_12"].to_numpy(dtype=float)))
    month = df["target_month_number"].to_numpy()
    cols += [(month == m).astype(float) for m in MONTHS]
    return np.column_stack(cols)


def fit(train_df: pd.DataFrame, prefix: str | None = None) -> PerTypeModel:
    glms = {}
    for t in config.TYPE_COLUMNS:
        X = design_matrix(train_df, t)
        glms[t] = PoissonRegressor(**config.GLM_PARAMS).fit(X, train_df[f"{t}_target"].to_numpy(dtype=float))
    return PerTypeModel(glms=glms, n_columns=X.shape[1])


def per_type(model: PerTypeModel, df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({t: np.clip(g.predict(design_matrix(df, t)), 0, None) for t, g in model.glms.items()},
                        index=df.index)


def predict(model: PerTypeModel, df: pd.DataFrame, prefix: str) -> np.ndarray:
    pt = per_type(model, df)
    if prefix == "wi":
        w = pd.Series(config.SEVERITY_WEIGHTS)[pt.columns]
        return (pt * w).sum(axis=1).to_numpy()
    return pt.sum(axis=1).to_numpy()


def n_params(model: PerTypeModel) -> int:
    return len(model.glms) * (model.n_columns + 1)
