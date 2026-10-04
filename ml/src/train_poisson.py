"""Poisson GLM (log link) for one target.

Design matrix:
  * log1p of last_value, mean_3, mean_6, mean_12, same_month_last_year
    (with a log link, log1p(features) makes the model multiplicative: the forecast scales with the
    area's own level; raw counts in a log-link model gave ~21 MAE instead of ~13 in the first draft)
  * one-hot target_month_number (12 columns): the seasonal adjustment
  * optionally one-hot neighbourhood (24 columns): a per-area level shift (variant 'poisson_glm_area')

Interface shared with train_rf.py:
    model = fit(train_df, prefix, use_area=False)
    yhat  = predict(model, df, prefix)               # numpy array, clipped at 0
    month_effects(model) -> {1: pct, ..., 12: pct}   # for the forecast drivers
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

import common  # noqa: F401  (sets up sys.path for config)
import config
from build_features import FEATURES

MONTHS = list(range(1, 13))


@dataclass
class GLMModel:
    glm: PoissonRegressor
    prefix: str
    use_area: bool
    areas: list[str]        # fixed, sorted list so the one-hot columns never change order
    columns: list[str]      # names of the design-matrix columns (for reading coefficients)


def design_matrix(df: pd.DataFrame, prefix: str, use_area: bool, areas: list[str]) -> tuple[np.ndarray, list[str]]:
    """Build the numeric matrix the GLM sees. Column order is fixed, so fit and predict always agree."""
    cols, names = [], []
    for f in FEATURES:
        x = df[f"{prefix}_{f}"].to_numpy(dtype=float)
        cols.append(np.log1p(x) if config.LOG1P_FEATURES_FOR_GLM else x)
        names.append(f"log1p_{f}" if config.LOG1P_FEATURES_FOR_GLM else f)
    month = df["target_month_number"].to_numpy()
    for m in MONTHS:
        cols.append((month == m).astype(float))
        names.append(f"month_{m}")
    if use_area:
        area = df[config.AREA_KEY].to_numpy()
        for a in areas:
            cols.append((area == a).astype(float))
            names.append(f"area_{a}")
    return np.column_stack(cols), names


def fit(train_df: pd.DataFrame, prefix: str, use_area: bool = False) -> GLMModel:
    areas = sorted(train_df[config.AREA_KEY].unique())
    X, names = design_matrix(train_df, prefix, use_area, areas)
    y = train_df[f"{prefix}_target"].to_numpy(dtype=float)
    glm = PoissonRegressor(**config.GLM_PARAMS).fit(X, y)
    return GLMModel(glm=glm, prefix=prefix, use_area=use_area, areas=areas, columns=names)


def predict(model: GLMModel, df: pd.DataFrame, prefix: str) -> np.ndarray:
    X, _ = design_matrix(df, prefix, model.use_area, model.areas)
    return np.clip(model.glm.predict(X), 0, None)


def month_effects(model: GLMModel) -> dict[int, float]:
    """Seasonal adjustment per target month, in % relative to the average of the 12 month effects.

    exp(coef_m - mean(coef)) - 1: e.g. +4.0 means the model multiplies a forecast for that month by
    about 1.04 compared with an average month, holding the area's recent levels fixed.
    """
    coefs = np.array([model.glm.coef_[model.columns.index(f"month_{m}")] for m in MONTHS])
    rel = np.exp(coefs - coefs.mean()) - 1.0
    return {m: float(r * 100.0) for m, r in zip(MONTHS, rel)}
