"""Random Forest for one target, on the same rows as the GLM.

Features: the raw (not log) last_value, mean_3, mean_6, mean_12, same_month_last_year,
target_month_number, and the neighbourhood as an integer code (position in the sorted list of
the 24 names, so the code never depends on row order). Parameters come from config.RF_PARAMS
(random_state fixed, so results are reproducible).

Interface shared with train_poisson.py:
    model = fit(train_df, prefix)
    yhat  = predict(model, df, prefix)
    lo, hi = tree_quantiles(model, df, prefix, level)   # tree-spread interval, for comparison only
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

import common  # noqa: F401  (sets up sys.path for config)
import config
from build_features import FEATURES


@dataclass
class RFModel:
    rf: RandomForestRegressor
    prefix: str
    areas: list[str]


def design_matrix(df: pd.DataFrame, prefix: str, areas: list[str]) -> np.ndarray:
    code = {a: i for i, a in enumerate(areas)}
    cols = [df[f"{prefix}_{f}"].to_numpy(dtype=float) for f in FEATURES]
    cols.append(df["target_month_number"].to_numpy(dtype=float))
    cols.append(df[config.AREA_KEY].map(code).to_numpy(dtype=float))
    return np.column_stack(cols)


def fit(train_df: pd.DataFrame, prefix: str) -> RFModel:
    areas = sorted(train_df[config.AREA_KEY].unique())
    X = design_matrix(train_df, prefix, areas)
    y = train_df[f"{prefix}_target"].to_numpy(dtype=float)
    rf = RandomForestRegressor(**config.RF_PARAMS).fit(X, y)
    return RFModel(rf=rf, prefix=prefix, areas=areas)


def predict(model: RFModel, df: pd.DataFrame, prefix: str) -> np.ndarray:
    return np.clip(model.rf.predict(design_matrix(df, prefix, model.areas)), 0, None)


def tree_quantiles(model: RFModel, df: pd.DataFrame, prefix: str, level: float) -> tuple[np.ndarray, np.ndarray]:
    """Interval from the spread of the individual trees' predictions. Reported for comparison only;
    the contract uses backtest ratios instead (see intervals.py)."""
    X = design_matrix(df, prefix, model.areas)
    per_tree = np.stack([t.predict(X) for t in model.rf.estimators_])
    a = (1 - level) / 2
    return np.quantile(per_tree, a, axis=0), np.quantile(per_tree, 1 - a, axis=0)
