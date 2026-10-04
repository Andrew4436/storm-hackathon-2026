"""Relative-activity tiers: one rule shared by history, evaluation and forecast.

A value is compared with the area's own "typical" level, defined as the mean of its trailing
config.TIER_WINDOW_MONTHS complete months. The percentage difference decides the tier:

    pct_vs_typical < low threshold   -> below_typical
    pct_vs_typical > high threshold  -> above_typical
    otherwise                        -> typical

Areas that average fewer than config.TIER_MIN_MEAN reported incidents per month over the same
window get "insufficient_data" (Musqueam): with counts that small, a few incidents swing the
percentage wildly and a tier would mean nothing.
"""
from __future__ import annotations

import math

import pandas as pd

import common  # noqa: F401  (sets up sys.path for config)
import config

TIERS = ["below_typical", "typical", "above_typical"]
INSUFFICIENT = "insufficient_data"
MIN_PRIOR_MONTHS = 12   # fewer complete months than this in the window -> no tier at all


def tier(value: float, typical_mean: float, area_mean_incidents: float) -> tuple[str | None, float | None]:
    """Return (tier, pct_vs_typical) for one value.

    value               the number being classified (a realised month or a forecast)
    typical_mean        trailing mean of the SAME series (weighted_index or incident_count)
    area_mean_incidents trailing mean of incident_count over the same window (used for the minimum-size rule)

    Returns (None, None) when there is no typical level yet (too little history),
    and ('insufficient_data', None) for very small areas.
    """
    if typical_mean is None or area_mean_incidents is None or pd.isna(typical_mean) or pd.isna(area_mean_incidents):
        return None, None
    if area_mean_incidents < config.TIER_MIN_MEAN or typical_mean <= 0:
        return INSUFFICIENT, None
    pct = (value - typical_mean) / typical_mean * 100.0
    low, high = config.TIER_THRESHOLDS_PCT
    if pct < low:
        label = "below_typical"
    elif pct > high:
        label = "above_typical"
    else:
        label = "typical"
    return label, pct


def trailing_mean(df: pd.DataFrame, value_col: str) -> pd.Series:
    """Each area's mean of `value_col` over the trailing TIER_WINDOW_MONTHS complete months,
    up to and INCLUDING each row's month.

    `df` must hold the full calendar (one row per area-month, sorted by area then month) with an
    `is_partial` column. Partial months are treated as missing, so they never enter a "typical" level.
    Needs at least MIN_PRIOR_MONTHS complete months in the window, otherwise NaN.

    For "the months BEFORE this one" (history mode), shift the result by one month within each area.
    """
    values = df[value_col].astype(float).where(df["is_partial"] == 0)
    return (
        values.groupby(df[config.AREA_KEY], sort=False)
        .rolling(config.TIER_WINDOW_MONTHS, min_periods=MIN_PRIOR_MONTHS)
        .mean()
        .reset_index(level=0, drop=True)
        .sort_index()
    )


def tier_frame(values, typical, area_means) -> pd.DataFrame:
    """Vectorised convenience: apply tier() row by row; returns columns tier, pct_vs_typical."""
    out = [tier(v, t, a) for v, t, a in zip(values, typical, area_means)]
    return pd.DataFrame(out, columns=["tier", "pct_vs_typical"])


def round_pct(pct: float | None) -> float | None:
    """pct_vs_typical is published to 1 decimal; None stays None."""
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return None
    return round(float(pct), 1)
