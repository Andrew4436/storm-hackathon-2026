"""Metrics shared by study.py and evaluate.py (regression, tier, paired month comparison, noise floor)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score

import common
import config
import tiers


def regression_metrics(df: pd.DataFrame, method: str) -> dict:
    df = df[df[method].notna()]
    err = df[method] - df["actual"]
    no_cbd = df[config.AREA_KEY] != common.CBD
    per_area = err.abs().groupby(df[config.AREA_KEY]).mean()
    per_area_m12 = (df["mean_12"] - df["actual"]).abs().groupby(df[config.AREA_KEY]).mean()
    return {
        "n": int(len(df)),
        "mae": float(err.abs().mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "wape_pct": float(err.abs().sum() / df["actual"].sum() * 100),
        "bias_pct": float(err.sum() / df["actual"].sum() * 100),
        "mae_excl_cbd": float(err[no_cbd].abs().mean()),
        "areas_beating_mean_12": int((per_area < per_area_m12).sum()),
    }


def tier_labels(df: pd.DataFrame, method: str, thresholds=None) -> tuple[pd.Series, pd.Series]:
    """(predicted, realised) tiers on rows where the realised tier is a real tier (not insufficient / None)."""
    pred = tiers.tier_frame(df[method], df["typical_mean"], df["area_mean_incidents"], thresholds)["tier"]
    true = tiers.tier_frame(df["actual"], df["typical_mean"], df["area_mean_incidents"], thresholds)["tier"]
    keep = true.isin(tiers.TIERS).to_numpy()
    return pred[keep].reset_index(drop=True), true[keep].reset_index(drop=True)


def tier_metrics(df: pd.DataFrame, method: str, thresholds=None) -> dict:
    """Predicted tier (from the forecast) vs realised tier (from the actual), same typical level at the origin."""
    df = df[df[method].notna()]
    pred, true = tier_labels(df, method, thresholds)
    rec = recall_score(true, pred, labels=tiers.TIERS, average=None, zero_division=0)
    shares = true.value_counts(normalize=True)
    out = {
        "tier_n": int(len(true)),
        "tier_accuracy": float((pred == true).mean()),
        "tier_macro_f1": float(f1_score(true, pred, labels=tiers.TIERS, average="macro", zero_division=0)),
        "tier_majority_baseline": float(shares.max()),
        "tier_majority_class": str(shares.idxmax()),
    }
    out.update({f"recall_{t}": float(r) for t, r in zip(tiers.TIERS, rec)})
    return out


def paired_months(df: pd.DataFrame, method: str, ref: str) -> dict:
    """Month-by-month: total |error| over the areas for `method` vs `ref` (negative diff = method better)."""
    df = df[df[method].notna()]
    e_m = (df[method] - df["actual"]).abs().groupby(df["target_month"]).sum()
    e_r = (df[ref] - df["actual"]).abs().groupby(df["target_month"]).sum()
    d = e_m - e_r
    sd = d.std(ddof=1)
    return {"months": int(len(d)), "months_better": int((d < 0).sum()), "mean_diff": float(d.mean()),
            "t_stat": float(d.mean() / (sd / np.sqrt(len(d)))) if sd > 0 else 0.0}


def noise_floor(features_rows: pd.DataFrame) -> dict:
    """Expected MAE of a PERFECT forecast (one that knew each month's true Poisson mean), for both targets.

    Each type count is treated as Poisson with mean = the realised count (a proxy for the true mean), so
    incident_count has variance sum(lambda_k) and weighted_index sum(w_k^2 lambda_k); E|X - mu| = sqrt(2 var / pi)
    (normal approximation). Real counts are over-dispersed (duplicated rows, clustered events), so this is a
    LOWER bound on irreducible error.
    """
    w = pd.Series(config.SEVERITY_WEIGHTS)
    lam = features_rows[[f"{t}_target" for t in config.TYPE_COLUMNS]].clip(lower=0.5)
    lam.columns = config.TYPE_COLUMNS
    var_ic = lam.sum(axis=1)
    var_wi = (lam * w[lam.columns] ** 2).sum(axis=1)
    return {
        "incident_count": float(np.sqrt(2 * var_ic / np.pi).mean()),
        "weighted_index": float(np.sqrt(2 * var_wi / np.pi).mean()),
    }


def typical_area_noise(monthly: pd.DataFrame, end_month: str) -> dict:
    """Poisson noise (sd / mean, %) of one month for the median area over the 12 months ending `end_month`."""
    last = monthly[(monthly[config.MONTH_KEY] <= end_month) & (monthly["is_partial"] == 0)]
    last = last[last[config.MONTH_KEY] > common.add_months(end_month, -12)]
    g = last.groupby(config.AREA_KEY)
    lam = g[config.TYPE_COLUMNS].mean()
    w = pd.Series(config.SEVERITY_WEIGHTS)[config.TYPE_COLUMNS]
    ic_pct = 100 / np.sqrt(lam.sum(axis=1))
    wi_pct = 100 * np.sqrt((lam * w ** 2).sum(axis=1)) / (lam * w).sum(axis=1)
    med_area = lam.sum(axis=1).sort_values().index[len(lam) // 2]
    return {"median_area": med_area, "median_area_incidents": float(lam.sum(axis=1)[med_area]),
            "incident_count_pct": float(ic_pct[med_area]), "weighted_index_pct": float(wi_pct[med_area]),
            "incident_count_pct_median_over_areas": float(ic_pct.median()),
            "weighted_index_pct_median_over_areas": float(wi_pct.median())}
