"""All forecasting methods in one registry, shared by study.py, evaluate.py and forecast.py.

Method names (columns of backtest_predictions.csv):

    mean_3, mean_12, same_month_last_year   baselines (baselines.py)
    poisson_glm        C0  reference GLM, the model shipped on 2026-10-03 (train_poisson.py, variant "base")
    poisson_glm_area       C0 + area one-hot (reported only)
    random_forest          Random Forest (train_rf.py, reported only)
    blend                  0.5 x C0 + 0.5 x mean_12 (reported only)
    per_type_glm       C1  one GLM per type, summed with the severity weights (train_pertype.py)
    glm_extended       C2  GLM with long-run, t-1 and momentum features (train_poisson.py, variant chosen on fold A)
    hgb_poisson        C3  Poisson gradient boosting on C2's raw features + area (train_hgb.py)
    hgb_glm_blend      C3b 0.5 x C3 + 0.5 x C2
    stacked_blend      C4  w1 x C1 + w2 x C2 + w3 x mean_12, weights fitted on fold A only
    area_corrected     C5  best of C1..C4 x per-area factor from fold A (fold B only)

Everything fold-A-fitted (C2 variant, C4 weights, C5 factors) is computed here from fold A rows only.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import baselines
import common
import config
import train_hgb
import train_pertype
import train_poisson
import train_rf

CANDIDATES = ["per_type_glm", "glm_extended", "hgb_poisson", "hgb_glm_blend", "stacked_blend", "area_corrected"]
LABEL = {
    "mean_3": "mean_3", "mean_12": "mean_12", "same_month_last_year": "same_month_last_year",
    "poisson_glm": "C0 poisson_glm (reference)", "poisson_glm_area": "poisson_glm_area",
    "random_forest": "random_forest", "blend": "blend (C0 + mean_12)",
    "per_type_glm": "C1 per_type_glm", "glm_extended": "C2 glm_extended", "hgb_poisson": "C3 hgb_poisson",
    "hgb_glm_blend": "C3b hgb_glm_blend", "stacked_blend": "C4 stacked_blend", "area_corrected": "C5 area_corrected",
}
METHOD_ORDER = ["mean_3", "mean_12", "same_month_last_year", "poisson_glm", "poisson_glm_area", "random_forest",
                "blend"] + CANDIDATES
STACK_COMPONENTS = ["per_type_glm", "glm_extended", "mean_12"]
BIAS_CLIP = (0.8, 1.25)
MIN_FORECAST_FOR_RATIO = 1.0


# --------------------------------------------------------------------------- base models
def fit_base(name: str, train: pd.DataFrame, prefix: str, c2_variant: str):
    """Fit one base model; returns (model, predict_fn, n_params)."""
    if name == "poisson_glm":
        m = train_poisson.fit(train, prefix, use_area=False, variant="base")
        return m, train_poisson.predict, train_poisson.n_params(m)
    if name == "poisson_glm_area":
        m = train_poisson.fit(train, prefix, use_area=True, variant="base")
        return m, train_poisson.predict, train_poisson.n_params(m)
    if name in ("glm_extended", "glm_extended_noTM", "glm_extended_TM"):
        variant = {"glm_extended": c2_variant, "glm_extended_noTM": "extended", "glm_extended_TM": "extended_tm"}[name]
        m = train_poisson.fit(train, prefix, use_area=False, variant=variant)
        return m, train_poisson.predict, train_poisson.n_params(m)
    if name == "random_forest":
        m = train_rf.fit(train, prefix)
        return m, train_rf.predict, int(sum(t.tree_.node_count for t in m.rf.estimators_))
    if name == "per_type_glm":
        m = train_pertype.fit(train, prefix)
        return m, train_pertype.predict, train_pertype.n_params(m)
    if name == "hgb_poisson":
        m = train_hgb.fit(train, prefix, type_momentum=(c2_variant == "extended_tm"))
        return m, train_hgb.predict, train_hgb.n_params(m)
    raise ValueError(f"unknown base model {name!r}")


# --------------------------------------------------------------------------- folds
def train_test_split(features: pd.DataFrame, fold: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = config.FOLDS[fold]
    tm = features["target_month"]
    return features[(tm >= config.TRAIN_START) & (tm < start)], features[(tm >= start) & (tm <= end)]


def mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))))


# --------------------------------------------------------------------------- fold-A-fitted pieces
def stack_weights(fold_a: pd.DataFrame) -> dict[str, float]:
    """Grid search (step 0.05) over non-negative weights summing to 1 that minimise fold A MAE."""
    steps = np.round(np.arange(0, 1.0001, 0.05), 2)
    best = (np.inf, None)
    cols = [fold_a[c].to_numpy(dtype=float) for c in STACK_COMPONENTS]
    y = fold_a["actual"].to_numpy(dtype=float)
    for w1, w2 in itertools.product(steps, steps):
        w3 = round(1 - w1 - w2, 2)
        if w3 < -1e-9:
            continue
        err = mae(y, w1 * cols[0] + w2 * cols[1] + w3 * cols[2])
        if err < best[0] - 1e-9:
            best = (err, (float(w1), float(w2), float(max(w3, 0.0))))
    return dict(zip(STACK_COMPONENTS, best[1]))


def area_factors(fold_a: pd.DataFrame, parent: str) -> dict[str, float]:
    keep = fold_a[parent] >= MIN_FORECAST_FOR_RATIO
    ratio = (fold_a.loc[keep, "actual"] / fold_a.loc[keep, parent]).groupby(fold_a.loc[keep, config.AREA_KEY]).median()
    return {a: float(np.clip(r, *BIAS_CLIP)) for a, r in ratio.items()}


def derive(df: pd.DataFrame, prefix: str, weights: dict[str, float] | None) -> pd.DataFrame:
    """Add the combinations that need no fitting beyond fold-A weights."""
    df["blend"] = 0.5 * df["poisson_glm"] + 0.5 * df["mean_12"]
    df["hgb_glm_blend"] = 0.5 * df["hgb_poisson"] + 0.5 * df["glm_extended"]
    if weights is not None:
        df["stacked_blend"] = sum(w * df[c] for c, w in weights.items())
    return df


# --------------------------------------------------------------------------- backtest
BASE_MODELS = ["poisson_glm", "poisson_glm_area", "random_forest", "per_type_glm", "glm_extended_noTM",
               "glm_extended_TM", "hgb_poisson"]


def run_backtest(features: pd.DataFrame, typical: pd.DataFrame, verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    """Every method on identical rows, both targets, both folds. Returns (backtest table, fold-A decisions)."""
    info = {"c2_variant": {}, "stack_weights": {}, "n_params": {}, "hgb_trees": {}}
    frames = []
    for target, p in common.PREFIX.items():
        per_fold = {}
        for fold in sorted(config.FOLDS):
            train, test = train_test_split(features, fold)
            out = test[[config.AREA_KEY, "origin_month", "target_month"]].copy()
            out.insert(0, "fold", fold)
            out.insert(0, "target", target)
            out["actual"] = test[f"{p}_target"].to_numpy()
            for name, fn in baselines.BASELINES.items():
                out[name] = fn(test, p)
            per_fold[fold] = (train, test, out)

        # C2 variant: fold A only.
        for fold, (train, test, out) in per_fold.items():
            for name in ["poisson_glm", "poisson_glm_area", "per_type_glm", "glm_extended_noTM", "glm_extended_TM"]:
                model, predict, k = fit_base(name, train, p, "extended")
                out[name] = predict(model, test, p)
                if fold == "B":
                    info["n_params"].setdefault(target, {})[name] = k
            rf, predict, k = fit_base("random_forest", train, p, "extended")
            out["random_forest"] = predict(rf, test, p)
            out["rf_tree_low"], out["rf_tree_high"] = train_rf.tree_quantiles(rf, test, p, config.INTERVAL_LEVEL)
            if fold == "B":
                info["n_params"][target]["random_forest"] = k
        a_out = per_fold["A"][2]
        variant = min(["extended", "extended_tm"], key=lambda v: (
            mae(a_out["actual"], a_out["glm_extended_noTM" if v == "extended" else "glm_extended_TM"]), v))
        info["c2_variant"][target] = variant
        for fold, (train, test, out) in per_fold.items():
            out["glm_extended"] = out["glm_extended_TM" if variant == "extended_tm" else "glm_extended_noTM"]
            model, predict, k = fit_base("hgb_poisson", train, p, variant)
            out["hgb_poisson"] = predict(model, test, p)
            info["hgb_trees"].setdefault(target, {})[fold] = model.n_iter
            if fold == "B":
                info["n_params"][target]["hgb_poisson"] = k
                info["n_params"][target]["glm_extended"] = info["n_params"][target][
                    "glm_extended_TM" if variant == "extended_tm" else "glm_extended_noTM"]
            if verbose:
                print(f"  {target:15s} fold {fold}: train {len(train):,} rows, test {len(test):,} rows, "
                      f"hgb trees {model.n_iter}")
        for fold in per_fold:
            derive(per_fold[fold][2], p, None)
        w = stack_weights(per_fold["A"][2])
        info["stack_weights"][target] = w
        for fold in per_fold:
            derive(per_fold[fold][2], p, w)
        npar = info["n_params"][target]
        npar["mean_12"] = 0
        npar["hgb_glm_blend"] = npar["hgb_poisson"] + npar["glm_extended"]
        npar["stacked_blend"] = npar["per_type_glm"] + npar["glm_extended"] + 2
        npar["blend"] = npar["poisson_glm"]
        frames += [per_fold[f][2] for f in sorted(per_fold)]

    bt = pd.concat(frames, ignore_index=True)
    bt = bt.merge(typical, on=[config.AREA_KEY, "origin_month"], how="left")
    bt["typical_mean"] = np.where(bt["target"] == "weighted_index", bt["wi_typical"], bt["ic_typical"])
    bt = bt.drop(columns=["wi_typical", "ic_typical"])
    bt["area_corrected"] = np.nan
    return bt, info


# --------------------------------------------------------------------------- selection rule
def fold_mae(bt: pd.DataFrame, target: str, fold: str, method: str) -> float:
    sub = bt[bt["target"] == target]
    if fold != "pooled":
        sub = sub[sub["fold"] == fold]
    sub = sub[sub[method].notna()]
    return mae(sub["actual"], sub[method])


def select(bt: pd.DataFrame, info: dict, pool: list[str], target: str = "weighted_index") -> dict:
    """The pre-registered rule (config.SELECTION_*), applied to the methods in `pool`."""
    ref = config.REFERENCE_MODEL
    ref_b, ref_p = fold_mae(bt, target, "B", ref), fold_mae(bt, target, "pooled", ref)
    rows, qualifiers = [], []
    for m in pool:
        b, p = fold_mae(bt, target, "B", m), fold_mae(bt, target, "pooled", m)
        gain_b = (ref_b - b) / ref_b * 100
        ok = gain_b >= config.SELECTION_MIN_FOLD_B_GAIN_PCT and p < ref_p
        rows.append({"method": m, "mae_B": b, "mae_pooled": p, "gain_B_pct": gain_b,
                     "gain_pooled_pct": (ref_p - p) / ref_p * 100, "n_params": info["n_params"][target].get(m),
                     "qualifies": ok})
        if ok:
            qualifiers.append(rows[-1])
    chosen, reason = ref, "no candidate qualified; the reference GLM stays"
    if qualifiers:
        best = min(qualifiers, key=lambda r: (r["mae_pooled"], r["method"]))
        near = [r for r in qualifiers if r["mae_pooled"] <= best["mae_pooled"] * (1 + config.SELECTION_TIE_PCT / 100)]
        simplest = min(near, key=lambda r: (r["n_params"], r["mae_pooled"], r["method"]))
        # C4's fold A is in-sample: it may only ship if it is also the best qualifier on fold B.
        if simplest["method"] == "stacked_blend" and simplest["mae_B"] > min(r["mae_B"] for r in qualifiers):
            others = [r for r in near if r["method"] != "stacked_blend"] or \
                     [r for r in qualifiers if r["method"] != "stacked_blend"]
            simplest = min(others, key=lambda r: (r["n_params"], r["mae_pooled"], r["method"])) if others else None
        if simplest is not None:
            chosen = simplest["method"]
            reason = (f"lowest pooled MAE among qualifiers: {best['method']}"
                      + ("" if chosen == best["method"] else f"; {chosen} is simpler and within "
                         f"{config.SELECTION_TIE_PCT:g}% of it"))
    return {"chosen": chosen, "reason": reason, "table": rows, "qualifiers": [r["method"] for r in qualifiers]}


def apply_area_correction(bt: pd.DataFrame, parent: str) -> dict[str, dict[str, float]]:
    """C5: fold A factors on `parent`, written into bt['area_corrected'] for fold B rows. Returns the factors."""
    factors = {}
    for target in config.TARGETS:
        a = bt[(bt["target"] == target) & (bt["fold"] == "A")]
        f = area_factors(a, parent)
        factors[target] = f
        idx = (bt["target"] == target) & (bt["fold"] == "B")
        bt.loc[idx, "area_corrected"] = bt.loc[idx, parent] * bt.loc[idx, config.AREA_KEY].map(f).fillna(1.0)
    return factors


# --------------------------------------------------------------------------- final fit
def final_predict(model_name: str, train: pd.DataFrame, origin: pd.DataFrame, prefix: str, decision: dict):
    """Fit `model_name` on `train` and forecast the `origin` rows. Returns (forecast array, glm for drivers or None)."""
    target = {v: k for k, v in common.PREFIX.items()}[prefix]
    c2_variant = decision["c2_variant"][target]
    parent = decision.get("area_correction_parent") if model_name == "area_corrected" else None
    name = parent or model_name

    cols = pd.DataFrame(index=origin.index)
    needed = {"blend": ["poisson_glm"], "hgb_glm_blend": ["hgb_poisson", "glm_extended"],
              "stacked_blend": ["per_type_glm", "glm_extended"]}.get(name, [name])
    glm_for_drivers = None
    for base in needed:
        model, predict, _ = fit_base(base, train, prefix, c2_variant)
        cols[base] = predict(model, origin, prefix)
        if base in ("poisson_glm", "glm_extended") and glm_for_drivers is None:
            glm_for_drivers = model
    cols["mean_12"] = baselines.mean_12(origin, prefix)
    if name == "blend":
        out = 0.5 * cols["poisson_glm"] + 0.5 * cols["mean_12"]
    elif name == "hgb_glm_blend":
        out = 0.5 * cols["hgb_poisson"] + 0.5 * cols["glm_extended"]
    elif name == "stacked_blend":
        out = sum(w * cols[c] for c, w in decision["stack_weights"][target].items())
    else:
        out = cols[name]
    out = np.asarray(out, dtype=float)
    if parent:
        f = decision["area_factors"][target]
        out = out * origin[config.AREA_KEY].map(f).fillna(1.0).to_numpy()
    return out, glm_for_drivers
