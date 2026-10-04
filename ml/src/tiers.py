"""Relative-activity tiers: one rule shared by history, evaluation, the tier study and the forecast.

A value for month M is compared with the area's own "typical" level, computed from the
config.TIER_WINDOW_MONTHS most recent COMPLETE months available before M:

    reference "trailing_mean": the mean of those months
    reference "seasonal":      the mean of the months in that window that share M's calendar month
                               (window 12 -> the same month one year earlier; 36 -> the last three Octobers)

History labels month M against the window ending at M-1; the forecast labels the forecast month against the
window ending at the last complete month (DATA_THROUGH; M-2, because September 2026 is partial); the backtest
labels target month T against the window ending at the origin month T-2, exactly like the forecast.

The percentage difference decides the tier:

    pct_vs_typical < low threshold   -> below_typical
    pct_vs_typical > high threshold  -> above_typical
    otherwise                        -> typical

Areas that average fewer than config.TIER_MIN_MEAN reported incidents per month over the trailing window get
"insufficient_data" (Musqueam): with counts that small a few incidents swing the percentage wildly.

Every function takes window / thresholds / reference as optional arguments (defaults from config), so the tier
study can try alternatives with the same code that produces the published files.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import common  # noqa: F401  (sets up sys.path for config)
import config

TIERS = ["below_typical", "typical", "above_typical"]
INSUFFICIENT = "insufficient_data"
MIN_PRIOR_MONTHS = 12   # fewer complete months than this in the window -> no tier at all
REFERENCES = ["trailing_mean", "seasonal"]


def tier(value: float, typical_mean: float, area_mean_incidents: float,
         thresholds: tuple[float, float] | None = None) -> tuple[str | None, float | None]:
    """Return (tier, pct_vs_typical) for one value.

    value               the number being classified (a realised month or a forecast)
    typical_mean        "typical" level of the SAME series (weighted_index or incident_count)
    area_mean_incidents trailing mean of incident_count over the window (used for the minimum-size rule)

    Returns (None, None) when there is no typical level yet (too little history),
    and ('insufficient_data', None) for very small areas.
    """
    if typical_mean is None or area_mean_incidents is None or pd.isna(typical_mean) or pd.isna(area_mean_incidents):
        return None, None
    if area_mean_incidents < config.TIER_MIN_MEAN or typical_mean <= 0:
        return INSUFFICIENT, None
    pct = (value - typical_mean) / typical_mean * 100.0
    low, high = thresholds if thresholds is not None else config.TIER_THRESHOLDS_PCT
    if pct < low:
        label = "below_typical"
    elif pct > high:
        label = "above_typical"
    else:
        label = "typical"
    return label, pct


def trailing_mean(df: pd.DataFrame, value_col: str, window: int | None = None) -> pd.Series:
    """Each area's mean of `value_col` over the trailing `window` complete months, up to and INCLUDING each row.

    `df` must hold the full calendar (one row per area-month, sorted by area then month) with an `is_partial`
    column. Partial months are treated as missing. Needs at least MIN_PRIOR_MONTHS complete months, else NaN.
    """
    window = window or config.TIER_WINDOW_MONTHS
    values = df[value_col].astype(float).where(df["is_partial"] == 0)
    return (
        values.groupby(df[config.AREA_KEY], sort=False)
        .rolling(window, min_periods=min(MIN_PRIOR_MONTHS, window))
        .mean()
        .reset_index(level=0, drop=True)
        .sort_index()
    )


def seasonal_mean(df: pd.DataFrame, value_col: str, lead: int, window: int | None = None) -> pd.Series:
    """For the window ending at each row's month m: mean of the values in that window that fall in the calendar
    month of m + lead (the month being labelled). All of them must be complete months, else NaN."""
    window = window or config.TIER_WINDOW_MONTHS
    values = df[value_col].astype(float).where(df["is_partial"] == 0)
    g = values.groupby(df[config.AREA_KEY], sort=False)
    # month m + lead - 12k lies in m-window+1..m  <=>  1 <= k <= (window + lead - 1) / 12
    ks = [k for k in range(1, 10) if 12 * k - lead >= 0 and 12 * k - lead <= window - 1]
    stacked = np.column_stack([g.shift(12 * k - lead).to_numpy() for k in ks])
    return pd.Series(stacked.mean(axis=1), index=df.index)   # NaN if any is missing


def typical_level(df: pd.DataFrame, value_col: str, lead: int, window: int | None = None,
                  reference: str | None = None) -> pd.Series:
    """Typical level for the month `lead` months after each row's month, from the window ending at the row."""
    reference = reference or config.TIER_REFERENCE
    if reference == "trailing_mean":
        return trailing_mean(df, value_col, window)
    if reference == "seasonal":
        return seasonal_mean(df, value_col, lead, window)
    raise ValueError(f"unknown tier reference {reference!r}")


def tier_frame(values, typical, area_means, thresholds: tuple[float, float] | None = None) -> pd.DataFrame:
    """Vectorised convenience: apply tier() row by row; returns columns tier, pct_vs_typical."""
    out = [tier(v, t, a, thresholds) for v, t, a in zip(values, typical, area_means)]
    return pd.DataFrame(out, columns=["tier", "pct_vs_typical"])


def history_tiers(monthly: pd.DataFrame, window: int | None = None, thresholds=None,
                  reference: str | None = None) -> pd.DataFrame:
    """Tier of every realised neighbourhood-month on weighted_index vs the window ending the month before.

    Partial months get no tier (about 70% of a month would always read as below_typical).
    """
    area = monthly[config.AREA_KEY]
    typical = typical_level(monthly, "weighted_index", 1, window, reference).groupby(area, sort=False).shift(1)
    size = trailing_mean(monthly, "incident_count", window).groupby(area, sort=False).shift(1)
    t = tier_frame(monthly["weighted_index"], typical, size, thresholds)
    partial = (monthly["is_partial"] == 1).to_numpy()
    t.loc[partial, "tier"] = None
    t.loc[partial, "pct_vs_typical"] = np.nan
    return t


def round_pct(pct: float | None) -> float | None:
    """pct_vs_typical is published to 1 decimal; None stays None."""
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return None
    return round(float(pct), 1)
