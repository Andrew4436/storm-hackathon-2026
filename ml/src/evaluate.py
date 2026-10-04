"""Step 2: backtest every method on identical rows -> metrics, backtest predictions and the model decision.

Folds (config.FOLDS) are split by TARGET month with an expanding window:
    train = feature rows with TRAIN_START <= target_month < fold start
    test  = feature rows with fold start <= target_month <= fold end
Every method (3 baselines, Poisson GLM with and without area one-hot, Random Forest, 50/50 blend of
GLM and mean_12) is scored on exactly the same test rows. "Pooled" = test rows of both folds together.

Decision rule (contract decision 4, config.DECISION_METRIC): the shipped model is whichever of
{Poisson GLM, Random Forest} has the lower pooled MAE on weighted_index. The GLM variant (with or
without the area one-hot) is picked first by the same metric.

Writes:
    ml/outputs/backtest_predictions.csv   one row per (target, fold, area, target month), one column per method
    ml/outputs/evaluation_metrics.csv     one row per (target, fold, method)
    ml/outputs/evaluation.json            decision, ranges, metrics, interval quantiles
    reports/evaluation.md                 the same in plain language

Run from the repo root:  python ml/src/evaluate.py
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score

import baselines
import common
import config
import intervals
import tiers
import train_poisson
import train_rf

GLM_VARIANTS = ["poisson_glm", "poisson_glm_area"]
METHOD_ORDER = ["mean_3", "mean_12", "same_month_last_year", "poisson_glm", "poisson_glm_area", "random_forest", "blend"]
FOLD_NAMES = sorted(config.FOLDS) + ["pooled"]
FORECAST_SECTION_START = "<!-- forecast-tier-distribution:start -->"
FORECAST_SECTION_END = "<!-- forecast-tier-distribution:end -->"


# --------------------------------------------------------------------------- data
def load_features() -> pd.DataFrame:
    return pd.read_csv(common.OUTPUTS / "features.csv", dtype={"origin_month": str, "target_month": str})


def typical_at_origin(monthly: pd.DataFrame) -> pd.DataFrame:
    """Per (area, origin month): trailing TIER_WINDOW_MONTHS mean ending at the origin, for both targets.

    This is the "typical" level both the predicted and the realised tier are measured against, so it
    only uses information available at forecast time.
    """
    out = monthly[[config.AREA_KEY, config.MONTH_KEY]].rename(columns={config.MONTH_KEY: "origin_month"})
    for target, p in common.PREFIX.items():
        out[f"{p}_typical"] = tiers.trailing_mean(monthly, target)
    out["area_mean_incidents"] = out["ic_typical"]
    return out


def train_test_split(features: pd.DataFrame, fold: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = config.FOLDS[fold]
    tm = features["target_month"]
    train = features[(tm >= config.TRAIN_START) & (tm < start)]
    test = features[(tm >= start) & (tm <= end)]
    return train, test


# --------------------------------------------------------------------------- backtest
def run_backtest(features: pd.DataFrame, typical: pd.DataFrame) -> pd.DataFrame:
    """Fit every model per (target, fold) and collect predictions on the test rows (blend added later)."""
    rows = []
    for target, p in common.PREFIX.items():
        for fold in sorted(config.FOLDS):
            train, test = train_test_split(features, fold)
            out = test[[config.AREA_KEY, "origin_month", "target_month"]].copy()
            out.insert(0, "fold", fold)
            out.insert(0, "target", target)
            out["actual"] = test[f"{p}_target"].to_numpy()
            for name, fn in baselines.BASELINES.items():
                out[name] = fn(test, p)
            out["poisson_glm"] = train_poisson.predict(train_poisson.fit(train, p, use_area=False), test, p)
            out["poisson_glm_area"] = train_poisson.predict(train_poisson.fit(train, p, use_area=True), test, p)
            rf = train_rf.fit(train, p)
            out["random_forest"] = train_rf.predict(rf, test, p)
            out["rf_tree_low"], out["rf_tree_high"] = train_rf.tree_quantiles(rf, test, p, config.INTERVAL_LEVEL)
            out = out.merge(
                typical[[config.AREA_KEY, "origin_month", f"{p}_typical", "area_mean_incidents"]]
                .rename(columns={f"{p}_typical": "typical_mean"}),
                on=[config.AREA_KEY, "origin_month"], how="left",
            )
            rows.append(out)
            print(f"  {target:15s} fold {fold}: train {len(train):,} rows, test {len(test):,} rows")
    return pd.concat(rows, ignore_index=True)


def fold_view(bt: pd.DataFrame, target: str, fold: str) -> pd.DataFrame:
    sub = bt[bt["target"] == target]
    return sub if fold == "pooled" else sub[sub["fold"] == fold]


# --------------------------------------------------------------------------- metrics
def regression_metrics(df: pd.DataFrame, method: str) -> dict:
    err = df[method] - df["actual"]
    no_cbd = df[config.AREA_KEY] != common.CBD
    per_area = err.abs().groupby(df[config.AREA_KEY]).mean()
    per_area_m12 = (df["mean_12"] - df["actual"]).abs().groupby(df[config.AREA_KEY]).mean()
    return {
        "n": int(len(df)),
        "mae": float(err.abs().mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "wape_pct": float(err.abs().sum() / df["actual"].sum() * 100),
        "mae_excl_cbd": float(err[no_cbd].abs().mean()),
        "areas_beating_mean_12": int((per_area < per_area_m12).sum()),
    }


def tier_metrics(df: pd.DataFrame, method: str) -> dict:
    """Predicted tier (from the forecast) vs realised tier (from the actual), same typical level at the origin."""
    pred = tiers.tier_frame(df[method], df["typical_mean"], df["area_mean_incidents"])["tier"]
    true = tiers.tier_frame(df["actual"], df["typical_mean"], df["area_mean_incidents"])["tier"]
    keep = (true != tiers.INSUFFICIENT).to_numpy() & true.notna().to_numpy()
    pred, true = pred[keep], true[keep]
    rec = recall_score(true, pred, labels=tiers.TIERS, average=None, zero_division=0)
    out = {
        "tier_n": int(keep.sum()),
        "tier_accuracy": float((pred == true).mean()),
        "tier_macro_f1": float(f1_score(true, pred, labels=tiers.TIERS, average="macro", zero_division=0)),
    }
    out.update({f"recall_{t}": float(r) for t, r in zip(tiers.TIERS, rec)})
    return out


def all_metrics(bt: pd.DataFrame) -> pd.DataFrame:
    records = []
    for target in config.TARGETS:
        for fold in FOLD_NAMES:
            df = fold_view(bt, target, fold)
            for method in METHOD_ORDER:
                rec = {"target": target, "fold": fold, "method": method}
                rec.update(regression_metrics(df, method))
                rec.update(tier_metrics(df, method))
                records.append(rec)
    return pd.DataFrame(records)


def metric(m: pd.DataFrame, target: str, fold: str, method: str, col: str) -> float:
    return float(m.loc[(m.target == target) & (m.fold == fold) & (m.method == method), col].iloc[0])


# --------------------------------------------------------------------------- intervals
def interval_summary(bt: pd.DataFrame, method: str) -> list[dict]:
    """Coverage of 80% ranges on the backtest: pooled ratios (in-sample), fold A ratios applied to
    fold B (out-of-sample), and Random Forest tree spread (for comparison)."""
    out = []
    for target in config.TARGETS:
        pooled = fold_view(bt, target, "pooled")
        a, b = fold_view(bt, target, "A"), fold_view(bt, target, "B")
        ri = intervals.fit_ratios(pooled["actual"], pooled[method])
        lo, hi = ri.apply(pooled[method])
        ri_a = intervals.fit_ratios(a["actual"], a[method])
        lo_b, hi_b = ri_a.apply(b[method])
        out.append({
            "target": target,
            "method": method,
            "q_low": ri.q_low,
            "q_high": ri.q_high,
            "n_ratios": ri.n_ratios,
            "coverage_pooled_in_sample": intervals.coverage(pooled["actual"], lo, hi),
            "coverage_fold_A_ratios_on_B": intervals.coverage(b["actual"], lo_b, hi_b),
            "coverage_rf_tree_spread_pooled": intervals.coverage(pooled["actual"], pooled["rf_tree_low"], pooled["rf_tree_high"]),
            "rf_tree_relative_width": float(((pooled["rf_tree_high"] - pooled["rf_tree_low"]) / pooled["random_forest"].clip(lower=1)).median()),
        })
    return out


# --------------------------------------------------------------------------- report helpers
def fmt(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def regression_table(m: pd.DataFrame, target: str) -> str:
    header = ["method", "MAE A", "MAE B", "MAE pooled", "RMSE pooled", "WAPE pooled", "MAE excl. CBD pooled",
              "areas beating mean_12 (A / B / pooled)"]
    rows = []
    for method in METHOD_ORDER:
        g = lambda fold, col: metric(m, target, fold, method, col)  # noqa: E731
        beats = " / ".join(str(int(g(f, "areas_beating_mean_12"))) for f in FOLD_NAMES)
        rows.append([method, fmt(g("A", "mae")), fmt(g("B", "mae")), f"**{fmt(g('pooled', 'mae'))}**",
                     fmt(g("pooled", "rmse")), fmt(g("pooled", "wape_pct")) + "%", fmt(g("pooled", "mae_excl_cbd")),
                     beats if method != "mean_12" else "-"])
    return md_table(header, rows)


def tier_table(m: pd.DataFrame, target: str) -> str:
    header = ["method", "accuracy", "macro-F1", "recall below", "recall typical", "recall above"]
    rows = []
    for method in METHOD_ORDER:
        g = lambda col: metric(m, target, "pooled", method, col)  # noqa: E731
        rows.append([method, fmt(g("tier_accuracy") * 100) + "%", fmt(g("tier_macro_f1"), 3),
                     fmt(g("recall_below_typical") * 100) + "%", fmt(g("recall_typical") * 100) + "%",
                     fmt(g("recall_above_typical") * 100) + "%"])
    return md_table(header, rows)


def realised_tier_counts(bt: pd.DataFrame, target: str) -> dict:
    df = fold_view(bt, target, "pooled")
    t = tiers.tier_frame(df["actual"], df["typical_mean"], df["area_mean_incidents"])["tier"]
    return {k: int(v) for k, v in t.value_counts().sort_index().items()}


def write_report(m: pd.DataFrame, bt: pd.DataFrame, info: dict, ivals: list[dict], path) -> None:
    wi, ic = "weighted_index", "incident_count"
    shipped, glm = info["shipped_model"], info["glm_variant"]
    g_wi, r_wi, m12_wi = (metric(m, wi, "pooled", x, "mae") for x in (glm, "random_forest", "mean_12"))
    g_ic, m12_ic = metric(m, ic, "pooled", glm, "mae"), metric(m, ic, "pooled", "mean_12", "mae")
    gain_wi = (m12_wi - g_wi) / m12_wi * 100
    gain_ic = (m12_ic - g_ic) / m12_ic * 100
    glm_beats = {f: metric(m, wi, f, glm, "mae") < metric(m, wi, f, "mean_12", "mae") for f in sorted(config.FOLDS)}
    areas_beat = int(metric(m, wi, "pooled", glm, "areas_beating_mean_12"))
    blend_wi = metric(m, wi, "pooled", "blend", "mae")

    if gain_wi < 5:
        lead = (f"The lead over the 12-month mean is **small**: {fmt(gain_wi)}% lower pooled MAE on weighted_index, "
                f"{fmt(gain_ic)}% on incident_count. A different test year could reverse it; the honest summary is "
                "that the GLM is about as accurate as a 12-month average, slightly better overall.")
    else:
        lead = (f"The GLM is {fmt(gain_wi)}% below the 12-month mean's pooled MAE on weighted_index "
                f"({fmt(gain_ic)}% on incident_count): a real but modest improvement.")
    for f, beats in glm_beats.items():
        if not beats:
            lead += (f" **In fold {f} ({config.FOLDS[f][0]}..{config.FOLDS[f][1]}) the 12-month mean was more accurate** "
                     f"(weighted_index MAE {fmt(metric(m, wi, f, 'mean_12', 'mae'))} vs GLM {fmt(metric(m, wi, f, glm, 'mae'))}), "
                     "so the pooled lead comes from the other fold.")
    fold_line = ", ".join(f"fold {f}: {'yes' if v else 'no'}" for f, v in glm_beats.items())

    ref = {"mean_3": 14.2, "mean_12": 13.7, "same_month_last_year": 17.0, "poisson_glm": 13.3,
           "random_forest": 14.8, "blend": 13.1}
    ref_rows = [[k, fmt(v), fmt(metric(m, ic, "pooled", k, "mae"))] for k, v in ref.items()]

    iv_rows = []
    for iv in ivals:
        iv_rows.append([iv["target"], iv["method"], f"{iv['q_low']:.3f} .. {iv['q_high']:.3f}",
                        fmt(iv["coverage_pooled_in_sample"] * 100) + "%",
                        fmt(iv["coverage_fold_A_ratios_on_B"] * 100) + "%",
                        fmt(iv["coverage_rf_tree_spread_pooled"] * 100) + "%"])

    split_rows = [[f, info["folds"][f]["train_targets"], str(info["folds"][f]["n_train"]),
                   info["folds"][f]["test_targets"], str(info["folds"][f]["n_test"])] for f in sorted(config.FOLDS)]

    realised = {t: realised_tier_counts(bt, t) for t in config.TARGETS}
    n_tiered = sum(realised[wi].get(k, 0) for k in tiers.TIERS)
    # The most common realised tier is the "always guess this" benchmark for tier accuracy.
    top_tier = max(tiers.TIERS, key=lambda k: (realised[wi].get(k, 0), k))
    top_share = realised[wi].get(top_tier, 0) / n_tiered * 100
    best_tier_method = max(METHOD_ORDER, key=lambda k: (metric(m, wi, "pooled", k, "tier_accuracy"), k))
    best_tier_acc = metric(m, wi, "pooled", best_tier_method, "tier_accuracy") * 100
    if best_tier_acc < top_share:
        constant_line = (f"Always predicting `{top_tier}` would score {fmt(top_share)}% accuracy, higher than every method "
                         f"here (best: {best_tier_method} at {fmt(best_tier_acc)}%), so tier accuracy should not be "
                         "presented as skill.")
    else:
        constant_line = (f"Always predicting `{top_tier}` would score {fmt(top_share)}% accuracy; the best method here "
                         f"({best_tier_method}) scores {fmt(best_tier_acc)}%.")

    # Every config value quoted in the prose below is read from config, so re-tuning it keeps the report consistent.
    window = config.TIER_WINDOW_MONTHS
    lo_pct, hi_pct = config.TIER_THRESHOLDS_PCT
    band = f"{lo_pct:+g}%..{hi_pct:+g}%"
    glm_wape = metric(m, wi, "pooled", glm, "wape_pct")
    if max(abs(t) for t in config.TIER_THRESHOLDS_PCT) < glm_wape:
        band_line = (f"with forecast errors of about {fmt(glm_wape, 0)}% (GLM WAPE above), "
                     f"a {band} band is narrower than the forecast error.")
    else:
        band_line = (f"forecast errors are about {fmt(glm_wape, 0)}% (GLM WAPE above), "
                     f"inside the {band} band.")
    fold_text = " and ".join(f"{a}..{b}" for _, (a, b) in sorted(config.FOLDS.items()))
    n_folds_word = {1: "One", 2: "Two", 3: "Three", 4: "Four"}.get(len(config.FOLDS), str(len(config.FOLDS)))
    monthly = common.load_monthly()
    partial = sorted(monthly.loc[monthly["is_partial"] == 1, config.MONTH_KEY].unique())
    partial_text = (", ".join(partial) + " (partial) is never used") if partial else "no month is partial"

    md = f"""# Evaluation: neighbourhood monthly forecast, horizon {config.HORIZON_MONTHS} months

Generated by `ml/src/evaluate.py` from `{config.PROCESSED_CSV}` (data through {config.DATA_THROUGH};
{config.FORECAST_MONTH} is forecast from it). All numbers are reported incidents per neighbourhood per month
or their severity-weighted index; nothing here is a rating of any place.

## Decision

- Rule (fixed before the run, `config.DECISION_METRIC = "{config.DECISION_METRIC}"`): ship whichever of
  Poisson GLM and Random Forest has the lower pooled MAE on `weighted_index`.
- GLM variant: `{glm}` (pooled weighted_index MAE {fmt(metric(m, wi, 'pooled', 'poisson_glm', 'mae'))} without the
  area one-hot vs {fmt(metric(m, wi, 'pooled', 'poisson_glm_area', 'mae'))} with it; lower wins).
- **Shipped model: `{shipped}`** (pooled weighted_index MAE: GLM {fmt(g_wi)}, Random Forest {fmt(r_wi)}).
- 12-month mean, for reference: {fmt(m12_wi)}. {lead}
- GLM beats the 12-month mean on weighted_index in each fold? {fold_line}. It beats it in {areas_beat} of 24 areas (pooled).
- Blend (0.5 x GLM + 0.5 x 12-month mean), reported only: pooled weighted_index MAE {fmt(blend_wi)}.

## Setup

- Target month T = origin month t + {config.HORIZON_MONTHS}. Features use months up to t only; {partial_text}.
- Expanding window, split by target month; training targets start at {config.TRAIN_START}.
- Every method is scored on identical test rows. "Pooled" = folds A and B together ({info['n_pooled']} rows per target).

{md_table(["fold", "train target months", "train rows", "test target months", "test rows"], split_rows)}

Metrics: MAE and RMSE in the target's units; WAPE = sum |error| / sum actual; MAE excl. CBD drops
Central Business District (roughly 4x any other area); "areas beating mean_12" counts the 24 areas whose
own MAE is below the 12-month mean's.

## Results: weighted_index (decision target)

{regression_table(m, wi)}

## Results: incident_count

{regression_table(m, ic)}

Check against the independent benchmark on incident_count (pooled MAE):

{md_table(["method", "benchmark", "this run"], ref_rows)}

## Tier metrics (pooled)

The predicted tier applies the tier rule to the forecast; the realised tier applies it to the actual value.
Both are measured against the same "typical" level: the area's mean over the {config.TIER_WINDOW_MONTHS} complete
months ending at the origin month. Thresholds {config.TIER_THRESHOLDS_PCT} %; areas averaging under
{config.TIER_MIN_MEAN} incidents/month are `insufficient_data` and excluded here.

Realised tiers in the pooled test set (how often each tier actually happened):

{md_table(["target"] + tiers.TIERS + [tiers.INSUFFICIENT], [[t] + [str(realised[t].get(k, 0)) for k in tiers.TIERS + [tiers.INSUFFICIENT]] for t in config.TARGETS])}

Read these with care: {fmt(top_share)}% of realised weighted_index tiers in the test folds ({fold_text}) are `{top_tier}`
(measured against each area's own {window}-month mean), so a forecast that mostly says that tier scores well.
{constant_line} The shipped GLM's tier accuracy of
{fmt(metric(m, wi, 'pooled', glm, 'tier_accuracy') * 100, 0)}% with macro-F1 {fmt(metric(m, wi, 'pooled', glm, 'tier_macro_f1'), 2)} means the predicted tier is a weak signal at the current thresholds;
{band_line} The thresholds are the team's call at the 7 PM checkpoint.

### weighted_index

{tier_table(m, wi)}

### incident_count

{tier_table(m, ic)}

## Uncertainty ranges ({int(config.INTERVAL_LEVEL * 100)}% nominal)

Shipped method: ratio actual / forecast pooled across areas and both folds; Q{round((1 - config.INTERVAL_LEVEL) / 2 * 100)} and
Q{round((1 + config.INTERVAL_LEVEL) / 2 * 100)} of that ratio multiply the forecast. Forecasts below
{intervals.MIN_FORECAST_FOR_RATIO:g} are left out of the ratios to avoid blow-ups. In-sample coverage is ~{int(config.INTERVAL_LEVEL * 100)}% by construction;
the fold A -> fold B column is the honest out-of-sample check. Random Forest tree spread is shown for
information only (the contract does not use it).

{md_table(["target", "method", "ratio Q-low .. Q-high", "coverage, pooled ratios (in-sample)",
           "coverage, fold A ratios on fold B", "coverage, RF tree spread"], iv_rows)}

## Forecast tier distribution

{FORECAST_SECTION_START}
_Filled in by `ml/src/forecast.py`._
{FORECAST_SECTION_END}

## Caveats

- {n_folds_word} test periods ({fold_text}) are a small sample; differences of a few percent in MAE between
  methods are not reliable.
- Recent months of Offence Against a Person are under-reported (reporting lag), which can pull fold B actuals down.
- Category mix shifts over time (Theft from Vehicle down, Other Theft up), so the weighted index and the count can move differently.
"""
    path.write_text(md, encoding="utf-8")


# --------------------------------------------------------------------------- main
def round_floats(obj, nd: int = 4):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: round_floats(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, nd) for v in obj]
    return obj


def main() -> None:
    t0 = time.time()
    features = load_features()
    typical = typical_at_origin(common.load_monthly())
    print("Backtesting ...")
    bt = run_backtest(features, typical)

    # 1. Pick the GLM variant, 2. build the blend from it, 3. apply the contract's decision rule.
    wi_mae = lambda method: float((bt.loc[bt.target == "weighted_index", method]  # noqa: E731
                                   - bt.loc[bt.target == "weighted_index", "actual"]).abs().mean())
    glm_variant = min(GLM_VARIANTS, key=lambda v: (wi_mae(v), v))
    bt["blend"] = 0.5 * bt[glm_variant] + 0.5 * bt["mean_12"]
    shipped = min([glm_variant, "random_forest"], key=lambda v: (wi_mae(v), v))

    metrics = all_metrics(bt)
    ivals = interval_summary(bt, shipped) + (interval_summary(bt, "random_forest") if shipped != "random_forest"
                                             else interval_summary(bt, glm_variant))

    folds_info = {}
    for fold in sorted(config.FOLDS):
        train, test = train_test_split(features, fold)
        folds_info[fold] = {
            "train_targets": f"{train['target_month'].min()}..{train['target_month'].max()}",
            "test_targets": f"{test['target_month'].min()}..{test['target_month'].max()}",
            "n_train": int(len(train)), "n_test": int(len(test)),
        }
    info = {
        "decision_metric": config.DECISION_METRIC,
        "glm_variant": glm_variant,
        "shipped_model": shipped,
        "mae_pooled_weighted_index": {k: wi_mae(k) for k in METHOD_ORDER},
        "folds": folds_info,
        "n_pooled": int((bt.target == "weighted_index").sum()),
        "train_start": config.TRAIN_START,
        "horizon_months": config.HORIZON_MONTHS,
        "data_through": config.DATA_THROUGH,
    }

    # ---- write outputs (rounded so files are readable and byte-stable)
    cols = ["target", "fold", config.AREA_KEY, "origin_month", "target_month", "actual", "typical_mean",
            "area_mean_incidents"] + METHOD_ORDER + ["rf_tree_low", "rf_tree_high"]
    bt[cols].round(4).to_csv(common.OUTPUTS / "backtest_predictions.csv", index=False)
    metrics.round(4).to_csv(common.OUTPUTS / "evaluation_metrics.csv", index=False)
    payload = {"decision": info, "intervals": ivals, "metrics": metrics.to_dict(orient="records")}
    (common.OUTPUTS / "evaluation.json").write_text(json.dumps(round_floats(payload), indent=2), encoding="utf-8")
    common.REPORTS.mkdir(parents=True, exist_ok=True)
    write_report(metrics, bt, info, ivals, common.REPORTS / "evaluation.md")

    # ---- console summary
    print("\nPooled MAE:")
    for target in config.TARGETS:
        row = {k: round(metric(metrics, target, "pooled", k, "mae"), 1) for k in METHOD_ORDER}
        print(f"  {target:15s} {row}")
    print(f"\nGLM variant: {glm_variant}   Shipped model: {shipped}")
    for iv in ivals:
        print(f"  interval {iv['target']:15s} {iv['method']:17s} ratios {iv['q_low']:.3f}..{iv['q_high']:.3f}  "
              f"coverage in-sample {iv['coverage_pooled_in_sample']:.1%}, A->B {iv['coverage_fold_A_ratios_on_B']:.1%}, "
              f"RF tree spread {iv['coverage_rf_tree_spread_pooled']:.1%}")
    print(f"evaluate.py done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
