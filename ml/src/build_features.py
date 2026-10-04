"""Step 1: processed csv -> ml/outputs/features.csv and ml/outputs/history.csv

features.csv: one row per (neighbourhood, origin month t, target month T = t + HORIZON_MONTHS).
For each aggregate target, prefixed wi_ (weighted_index) and ic_ (incident_count):

    <p>_last_value               value at t
    <p>_prev_value               value at t-1 (the second most recent month; "lag_2" in the study)
    <p>_mean_3/_6/_12/_24/_36    mean over the k months ending at t (t-k+1 .. t)
    <p>_same_month_last_year     value at T-12
    <p>_city_momentum            city-wide (sum of the 24 areas) mean_3 / mean_12 at t
    <p>_target                   value at T (what we try to forecast)

For each of the 8 types (column names as in the processed csv, e.g. other_theft_mean_3):
    <type>_last_value, <type>_mean_3, <type>_mean_6, <type>_mean_12, <type>_same_month_last_year, <type>_target

    target_month_number          calendar month of T (1-12)

Every feature uses only months <= t, so nothing from the target month or later leaks in.
Partial months (is_partial = 1, i.e. 2026-09) are set to missing BEFORE the features are built,
so any row whose window or target touches them drops out, as do rows without 36 months of lags
(origins before 2005-12; training targets start in 2010, so no training row is lost) and rows whose
target month is beyond the data.

history.csv: one row per neighbourhood-month with its tier (tiers.history_tiers, config tier settings).

Run from the repo root:  python ml/src/build_features.py
"""
from __future__ import annotations

import pandas as pd

import common
import config
import tiers

FEATURES = ["last_value", "mean_3", "mean_6", "mean_12", "same_month_last_year"]        # C0 GLM / RF
EXTENDED = ["mean_24", "prev_value", "mean_36"]                                          # extra counts (C2, C3)
TYPE_FEATURES = ["last_value", "mean_3", "mean_6", "mean_12", "same_month_last_year"]   # per type (C1)
assert [f"mean_{k}" for k in config.LAG_WINDOWS] == ["mean_3", "mean_6", "mean_12"], "FEATURES assumes LAG_WINDOWS = [3, 6, 12]"
assert config.LONG_WINDOWS == [24, 36], "EXTENDED assumes LONG_WINDOWS = [24, 36]"
assert 1 <= config.HORIZON_MONTHS <= 12, "same_month_last_year must lie at or before the origin month"


def feature_cols(prefix: str) -> list[str]:
    """['wi_last_value', 'wi_mean_3', ...] for a target prefix."""
    return [f"{prefix}_{f}" for f in FEATURES]


def series_features(values: pd.Series, area: pd.Series, name: str, windows: list[int], extended: bool) -> dict:
    """Lag features of one series (already NaN on partial months), keyed '<name>_<feature>'."""
    h = config.HORIZON_MONTHS
    g = values.groupby(area, sort=False)
    out = {f"{name}_last_value": values}
    for k in windows:
        # min_periods = k: a window with any missing month gives NaN (dropped below).
        out[f"{name}_mean_{k}"] = g.rolling(k, min_periods=k).mean().reset_index(level=0, drop=True).sort_index()
    # Value at T-12 = t + h - 12, i.e. (12 - h) months before the origin.
    out[f"{name}_same_month_last_year"] = g.shift(12 - h)
    if extended:
        out[f"{name}_prev_value"] = g.shift(1)
    out[f"{name}_target"] = g.shift(-h)
    return out


def make_feature_table(monthly: pd.DataFrame) -> pd.DataFrame:
    """All origin months, including ones whose target is unknown (target = NaN).

    The forecast step uses the row at origin = DATA_THROUGH from this table; features.csv keeps only
    rows with a known target.
    """
    area = monthly[config.AREA_KEY]
    h = config.HORIZON_MONTHS
    out = pd.DataFrame({config.AREA_KEY: area, "origin_month": monthly[config.MONTH_KEY]})
    # Target month = origin + horizon. The calendar is complete, so a shift of h rows is h months.
    out["target_month"] = [common.add_months(m, h) for m in out["origin_month"]]
    out["target_month_number"] = out["target_month"].str[5:7].astype(int)
    complete = monthly["is_partial"] == 0

    cols = {}
    for target, p in common.PREFIX.items():
        # Partial months become NaN, so they can never be a feature or a target.
        v = monthly[target].astype(float).where(complete)
        cols.update(series_features(v, area, p, config.LAG_WINDOWS + config.LONG_WINDOWS, extended=True))
        # City-wide momentum at the origin: one value per month, shared by all areas.
        city = v.groupby(monthly[config.MONTH_KEY]).sum(min_count=len(area.unique()))
        city = city.where(city > 0)
        ratio = (city.rolling(3, min_periods=3).mean() / city.rolling(12, min_periods=12).mean())
        cols[f"{p}_city_momentum"] = monthly[config.MONTH_KEY].map(ratio).astype(float)
    for t in config.TYPE_COLUMNS:
        v = monthly[t].astype(float).where(complete)
        cols.update(series_features(v, area, t, config.LAG_WINDOWS, extended=False))
    out = pd.concat([out, pd.DataFrame(cols, index=out.index)], axis=1)

    # Drop rows that lack any feature (the first 36 months of each area, and windows touching 2026-09).
    all_features = [c for c in out.columns if c not in (config.AREA_KEY, "origin_month", "target_month")
                    and not c.endswith("_target")]
    out = out.dropna(subset=all_features)
    return out.sort_values([config.AREA_KEY, "origin_month"]).reset_index(drop=True)


def make_history(monthly: pd.DataFrame) -> pd.DataFrame:
    """Per neighbourhood-month value + relative-activity tier (config window / thresholds / reference).

    The tier is computed on weighted_index (the primary target); the minimum-size rule uses incident_count.
    The partial month 2026-09 gets no tier.
    """
    t = tiers.history_tiers(monthly)
    return pd.DataFrame({
        "month_str": monthly[config.MONTH_KEY],
        config.AREA_KEY: monthly[config.AREA_KEY],
        "weighted_index": monthly["weighted_index"],
        "incident_count": monthly["incident_count"],
        "is_partial": monthly["is_partial"],
        "relative_activity_tier": t["tier"],
        "pct_vs_typical": [tiers.round_pct(x) for x in t["pct_vs_typical"]],
    })


def main() -> None:
    common.OUTPUTS.mkdir(parents=True, exist_ok=True)
    monthly = common.load_monthly()

    table = make_feature_table(monthly)
    target_cols = [c for c in table.columns if c.endswith("_target")]
    features = table.dropna(subset=target_cols).reset_index(drop=True)
    features.round(6).to_csv(common.OUTPUTS / "features.csv", index=False)

    history = make_history(monthly)
    history.to_csv(common.OUTPUTS / "history.csv", index=False)

    print(f"features.csv: {len(features):,} rows x {features.shape[1]} columns, "
          f"target months {features['target_month'].min()}..{features['target_month'].max()}")
    print(f"history.csv:  {len(history):,} rows (tiers: window {config.TIER_WINDOW_MONTHS}, "
          f"thresholds {config.TIER_THRESHOLDS_PCT}, reference {config.TIER_REFERENCE})")
    print("history tier counts (all months):")
    print(history["relative_activity_tier"].fillna("(none)").value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
