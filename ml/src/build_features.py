"""Step 1: processed csv -> ml/outputs/features.csv and ml/outputs/history.csv

features.csv: one row per (neighbourhood, origin month t, target month T = t + HORIZON_MONTHS),
with the same feature set for both targets, prefixed wi_ (weighted_index) and ic_ (incident_count):

    <p>_last_value            value at t
    <p>_mean_3/_mean_6/_mean_12  mean over the LAG_WINDOWS months ending at t (t-k+1 .. t)
    <p>_same_month_last_year  value at T-12
    <p>_target                value at T (what we try to forecast)
    target_month_number       calendar month of T (1-12)

Every feature uses only months <= t, so nothing from the target month or later leaks in.
Partial months (is_partial = 1, i.e. 2026-09) are set to missing BEFORE the features are built,
so any row whose window or target touches them drops out, as do rows without 12 months of lags
and rows whose target month is beyond the data.

history.csv: one row per neighbourhood-month with its tier relative to the trailing
TIER_WINDOW_MONTHS complete months BEFORE that month.

Run from the repo root:  python ml/src/build_features.py
"""
from __future__ import annotations

import pandas as pd

import common
import config
import tiers

FEATURES = ["last_value", "mean_3", "mean_6", "mean_12", "same_month_last_year"]
assert [f"mean_{k}" for k in config.LAG_WINDOWS] == ["mean_3", "mean_6", "mean_12"], "FEATURES assumes LAG_WINDOWS = [3, 6, 12]"
assert 1 <= config.HORIZON_MONTHS <= 12, "same_month_last_year must lie at or before the origin month"


def feature_cols(prefix: str) -> list[str]:
    """['wi_last_value', 'wi_mean_3', ...] for a target prefix."""
    return [f"{prefix}_{f}" for f in FEATURES]


def make_feature_table(monthly: pd.DataFrame) -> pd.DataFrame:
    """All origin months, including ones whose target is unknown (target = NaN).

    The forecast step uses the row at origin = DATA_THROUGH from this table; features.csv keeps only
    rows with a known target.
    """
    area = monthly[config.AREA_KEY]
    h = config.HORIZON_MONTHS
    out = pd.DataFrame({
        config.AREA_KEY: area,
        "origin_month": monthly[config.MONTH_KEY],
    })
    # Target month = origin + horizon. The calendar is complete, so a shift of h rows is h months.
    out["target_month"] = [common.add_months(m, h) for m in out["origin_month"]]
    out["target_month_number"] = out["target_month"].str[5:7].astype(int)

    for target, p in common.PREFIX.items():
        # Partial months become NaN, so they can never be a feature or a target.
        v = monthly[target].astype(float).where(monthly["is_partial"] == 0)
        g = v.groupby(area, sort=False)
        out[f"{p}_last_value"] = v
        for k in config.LAG_WINDOWS:
            # min_periods = k: a window with any missing month gives NaN (dropped below).
            out[f"{p}_mean_{k}"] = g.rolling(k, min_periods=k).mean().reset_index(level=0, drop=True).sort_index()
        # Value at T-12 = t + h - 12, i.e. (12 - h) months before the origin.
        out[f"{p}_same_month_last_year"] = g.shift(12 - h)
        out[f"{p}_target"] = g.shift(-h)

    # Drop rows that lack any lag (the first 12 months of each area, and windows touching 2026-09).
    all_features = [c for p in common.PREFIX.values() for c in feature_cols(p)]
    out = out.dropna(subset=all_features)
    return out.sort_values([config.AREA_KEY, "origin_month"]).reset_index(drop=True)


def make_history(monthly: pd.DataFrame) -> pd.DataFrame:
    """Per neighbourhood-month value + relative-activity tier vs the PREVIOUS TIER_WINDOW_MONTHS complete months.

    The tier is computed on weighted_index (the primary target); the minimum-size rule uses incident_count.
    The partial month 2026-09 gets no tier: comparing ~70% of a month with full months would always
    read as below_typical, which is an artefact of the data cut-off, not activity.
    """
    area = monthly[config.AREA_KEY]
    # trailing_mean includes the current month; shift by one month within each area for "before this month".
    typical_wi = tiers.trailing_mean(monthly, "weighted_index").groupby(area, sort=False).shift(1)
    typical_ic = tiers.trailing_mean(monthly, "incident_count").groupby(area, sort=False).shift(1)
    t = tiers.tier_frame(monthly["weighted_index"], typical_wi, typical_ic)
    hist = pd.DataFrame({
        "month_str": monthly[config.MONTH_KEY],
        config.AREA_KEY: area,
        "weighted_index": monthly["weighted_index"],
        "incident_count": monthly["incident_count"],
        "is_partial": monthly["is_partial"],
        "relative_activity_tier": t["tier"],
        "pct_vs_typical": [tiers.round_pct(x) for x in t["pct_vs_typical"]],
    })
    partial = hist["is_partial"] == 1
    hist.loc[partial, "relative_activity_tier"] = None
    hist.loc[partial, "pct_vs_typical"] = None
    return hist


def main() -> None:
    common.OUTPUTS.mkdir(parents=True, exist_ok=True)
    monthly = common.load_monthly()

    table = make_feature_table(monthly)
    target_cols = [f"{p}_target" for p in common.PREFIX.values()]
    features = table.dropna(subset=target_cols).reset_index(drop=True)
    features.to_csv(common.OUTPUTS / "features.csv", index=False)

    history = make_history(monthly)
    history.to_csv(common.OUTPUTS / "history.csv", index=False)

    print(f"features.csv: {len(features):,} rows, target months {features['target_month'].min()}..{features['target_month'].max()}")
    print(f"history.csv:  {len(history):,} rows")
    print("history tier counts (all months):")
    print(history["relative_activity_tier"].fillna("(none)").value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
