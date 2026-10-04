"""Candidate C3: HistGradientBoostingRegressor with a Poisson loss on C2's raw features + area code.

Features (raw, not log): last_value, prev_value, mean_3, mean_6, mean_12, mean_24, mean_36, same_month_last_year,
city_momentum, the type-momentum ratios (if `type_momentum`), target_month_number and the area as a categorical code.

Early stopping is time-ordered (sklearn's built-in early stopping holds out a RANDOM fraction, which would let
the model peek at months interleaved with its training months): the last config.HGB_VALIDATION_MONTHS target
months of the training rows are held out, the model grows in steps of HGB_ITER_STEP trees up to HGB_MAX_ITER,
the number of trees with the lowest validation Poisson deviance is kept, and the model is refitted on all
training rows with that many trees. Deterministic (random_state fixed, no subsampling).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_poisson_deviance

import common  # noqa: F401  (sets up sys.path for config)
import config
from build_features import EXTENDED, FEATURES
from train_poisson import type_momentum


@dataclass
class HGBModel:
    hgb: HistGradientBoostingRegressor
    areas: list[str]
    type_momentum: bool
    n_iter: int


def design_matrix(df: pd.DataFrame, prefix: str, areas: list[str], use_tm: bool) -> np.ndarray:
    code = {a: i for i, a in enumerate(areas)}
    cols = [df[f"{prefix}_{f}"].to_numpy(dtype=float) for f in FEATURES + EXTENDED]
    cols.append(df[f"{prefix}_city_momentum"].to_numpy(dtype=float))
    if use_tm:
        cols += [type_momentum(df, t) for t in config.MOMENTUM_TYPES]
    cols.append(df["target_month_number"].to_numpy(dtype=float))
    cols.append(df[config.AREA_KEY].map(code).to_numpy(dtype=float))
    return np.column_stack(cols)


def _new(n_iter: int, n_cols: int, warm: bool) -> HistGradientBoostingRegressor:
    cat = np.zeros(n_cols, dtype=bool)
    cat[-1] = True   # area code
    return HistGradientBoostingRegressor(max_iter=n_iter, early_stopping=False, warm_start=warm,
                                         categorical_features=cat, **config.HGB_PARAMS)


def fit(train_df: pd.DataFrame, prefix: str, type_momentum: bool = False) -> HGBModel:
    areas = sorted(train_df[config.AREA_KEY].unique())
    months = sorted(train_df["target_month"].unique())
    cut = months[-config.HGB_VALIDATION_MONTHS]
    head, tail = train_df[train_df["target_month"] < cut], train_df[train_df["target_month"] >= cut]
    Xh, Xt = design_matrix(head, prefix, areas, type_momentum), design_matrix(tail, prefix, areas, type_momentum)
    yh, yt = head[f"{prefix}_target"].to_numpy(dtype=float), tail[f"{prefix}_target"].to_numpy(dtype=float)

    model = _new(config.HGB_ITER_STEP, Xh.shape[1], warm=True)
    best = (np.inf, config.HGB_ITER_STEP)
    for n in range(config.HGB_ITER_STEP, config.HGB_MAX_ITER + 1, config.HGB_ITER_STEP):
        model.set_params(max_iter=n)
        model.fit(Xh, yh)
        dev = mean_poisson_deviance(yt, np.clip(model.predict(Xt), 1e-6, None))
        if dev < best[0] - 1e-12:
            best = (dev, n)

    X = design_matrix(train_df, prefix, areas, type_momentum)
    final = _new(best[1], X.shape[1], warm=False).fit(X, train_df[f"{prefix}_target"].to_numpy(dtype=float))
    return HGBModel(hgb=final, areas=areas, type_momentum=type_momentum, n_iter=best[1])


def predict(model: HGBModel, df: pd.DataFrame, prefix: str) -> np.ndarray:
    return np.clip(model.hgb.predict(design_matrix(df, prefix, model.areas, model.type_momentum)), 0, None)


def n_params(model: HGBModel) -> int:
    """Nodes across all trees (a rough size measure for the 'simpler model' tie-break)."""
    return int(sum(p.nodes.shape[0] for preds in model.hgb._predictors for p in preds))
