"""Baselines: the simple rules every model must beat, evaluated on the same rows as the models.

Each function takes the features frame (from build_features) and a target prefix ('wi' or 'ic')
and returns a numpy array of predictions, one per row.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def mean_3(df: pd.DataFrame, prefix: str) -> np.ndarray:
    """Mean of the 3 months ending at the origin (t-2..t)."""
    return df[f"{prefix}_mean_3"].to_numpy(dtype=float)


def mean_12(df: pd.DataFrame, prefix: str) -> np.ndarray:
    """Mean of the 12 months ending at the origin (t-11..t). The bar to beat at horizon 2."""
    return df[f"{prefix}_mean_12"].to_numpy(dtype=float)


def same_month_last_year(df: pd.DataFrame, prefix: str) -> np.ndarray:
    """Value in the target's calendar month one year earlier (T-12)."""
    return df[f"{prefix}_same_month_last_year"].to_numpy(dtype=float)


BASELINES = {"mean_3": mean_3, "mean_12": mean_12, "same_month_last_year": same_month_last_year}
