"""Step 2: backtest every method on identical rows -> metrics, backtest predictions, the model decision and the
judge-facing report.

Runs study.py's model and tier studies (so reports/model_study.md is regenerated with every run), then:
    ml/outputs/backtest_predictions.csv   one row per (target, fold, area, target month), one column per method
    ml/outputs/evaluation_metrics.csv     one row per (target, fold, method): regression + tier metrics
    ml/outputs/evaluation.json            decision, ranges, metrics, interval quantiles, noise floor
    reports/evaluation.md                 plain-language report (forecast.py fills the forecast-tier section)

Folds (config.FOLDS) are split by TARGET month with an expanding window; "pooled" = both folds together.
The shipped model is chosen by the pre-registered rule in config.SELECTION_* (see candidates.select).

Run from the repo root:  python ml/src/evaluate.py
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

import candidates
import common
import config
import intervals
import metrics
import study
import tiers

FOLD_NAMES = sorted(config.FOLDS) + ["pooled"]
FORECAST_SECTION_START = "<!-- forecast-tier-distribution:start -->"
FORECAST_SECTION_END = "<!-- forecast-tier-distribution:end -->"
METHOD_ORDER = candidates.METHOD_ORDER
REFERENCE_NUMBERS_IC = {"mean_3": 14.2, "mean_12": 13.7, "same_month_last_year": 17.0, "poisson_glm": 13.3,
                        "random_forest": 14.8, "blend": 13.1}
MODEL_DESCRIPTIONS = {
    "poisson_glm": ("Poisson regression (log link) on each area's recent levels (last month, 3-, 6- and 12-month "
                    "averages, same month last year, all as log1p) plus a calendar-month effect, fitted on 2010-2026 "
                    "across all 24 neighbourhoods."),
    "glm_extended": "Poisson regression with recent, long-run (24/36-month) and city-wide momentum features plus a calendar-month effect.",
    "per_type_glm": "One Poisson regression per reported-incident type, combined with the severity weights.",
    "hgb_poisson": "Gradient-boosted trees with a Poisson loss on recent and long-run levels, momentum, month and area.",
    "hgb_glm_blend": "Average of gradient-boosted trees and the extended Poisson regression.",
    "stacked_blend": "Weighted average of per-type regressions, the extended regression and the 12-month mean (weights from 2025).",
    "area_corrected": "Extended Poisson regression with a per-area correction factor learned on 2025.",
    "random_forest": "Random Forest on recent levels, month and area.",
}


def load_features() -> pd.DataFrame:
    return study.load_features()


def fold_view(bt: pd.DataFrame, target: str, fold: str) -> pd.DataFrame:
    return study.fold_view(bt, target, fold)


# --------------------------------------------------------------------------- metrics
def all_metrics(bt: pd.DataFrame) -> pd.DataFrame:
    records = []
    for target in config.TARGETS:
        for fold in FOLD_NAMES:
            df = fold_view(bt, target, fold)
            for method in METHOD_ORDER:
                if df[method].notna().sum() == 0:
                    continue
                rec = {"target": target, "fold": fold, "method": method}
                rec.update(metrics.regression_metrics(df, method))
                rec.update(metrics.tier_metrics(df, method))
                records.append(rec)
    return pd.DataFrame(records)


def metric(m: pd.DataFrame, target: str, fold: str, method: str, col: str) -> float:
    s = m.loc[(m.target == target) & (m.fold == fold) & (m.method == method), col]
    return float(s.iloc[0]) if len(s) else float("nan")


# --------------------------------------------------------------------------- intervals
def interval_summary(bt: pd.DataFrame, method: str) -> list[dict]:
    """Coverage of 80% ranges on the backtest: pooled ratios (in-sample), fold A ratios applied to fold B
    (out-of-sample), and Random Forest tree spread (for comparison)."""
    out = []
    for target in config.TARGETS:
        pooled = fold_view(bt, target, "pooled")
        a, b = fold_view(bt, target, "A"), fold_view(bt, target, "B")
        ri = intervals.fit_ratios(pooled["actual"], pooled[method])
        lo, hi = ri.apply(pooled[method])
        ri_a = intervals.fit_ratios(a["actual"], a[method])
        lo_b, hi_b = ri_a.apply(b[method])
        out.append({
            "target": target, "method": method, "q_low": ri.q_low, "q_high": ri.q_high, "n_ratios": ri.n_ratios,
            "coverage_pooled_in_sample": intervals.coverage(pooled["actual"], lo, hi),
            "coverage_fold_A_ratios_on_B": intervals.coverage(b["actual"], lo_b, hi_b),
            "coverage_rf_tree_spread_pooled": intervals.coverage(pooled["actual"], pooled["rf_tree_low"], pooled["rf_tree_high"]),
            "median_relative_width_pct": float((ri.q_high - ri.q_low) * 100),
        })
    return out


# --------------------------------------------------------------------------- report
def fmt(x: float, nd: int = 1) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{nd}f}"


md_table = study.md_table


def tier_table(m: pd.DataFrame, target: str, methods: list[str]) -> str:
    rows = []
    for method in methods:
        g = lambda col: metric(m, target, "pooled", method, col)  # noqa: E731
        rows.append([candidates.LABEL[method], fmt(g("tier_accuracy") * 100) + "%", fmt(g("tier_macro_f1"), 3),
                     fmt(g("recall_below_typical") * 100) + "%", fmt(g("recall_typical") * 100) + "%",
                     fmt(g("recall_above_typical") * 100) + "%"])
    return md_table(["method", "accuracy", "macro-F1", "recall below", "recall typical", "recall above"], rows)


def tier_phrase() -> str:
    lo, hi = config.TIER_THRESHOLDS_PCT
    if config.TIER_REFERENCE == "seasonal" and config.TIER_WINDOW_MONTHS == 12:
        ref = "the same calendar month one year earlier"
    elif config.TIER_REFERENCE == "seasonal":
        ref = (f"the average of the same calendar month over the last {config.TIER_WINDOW_MONTHS // 12} years "
               f"(within the last {config.TIER_WINDOW_MONTHS} complete months)")
    else:
        ref = f"the average of the last {config.TIER_WINDOW_MONTHS} complete months"
    return (f"`above_typical` if more than {hi:g}% above {ref}, `below_typical` if more than {abs(lo):g}% below it, "
            f"otherwise `typical`")


def write_report(m: pd.DataFrame, bt: pd.DataFrame, info: dict, ivals: list[dict], decision: dict, path) -> None:
    wi, ic = "weighted_index", "incident_count"
    ship, ref = info["shipped_model"], config.REFERENCE_MODEL
    p = lambda method, col="mae", fold="pooled", t=wi: metric(m, t, fold, method, col)  # noqa: E731
    mt = decision["metrics_table"]
    iv = next(x for x in ivals if x["target"] == wi and x["method"] == ship)
    iv_ic = next(x for x in ivals if x["target"] == ic and x["method"] == ship)
    floor = decision["noise_floor_mae"]
    noise = decision["typical_area_noise"]
    tc = decision["tier_choice"] or {}
    avg_actual_wi = fold_view(bt, wi, "pooled")["actual"].mean()
    avg_actual_ic = fold_view(bt, ic, "pooled")["actual"].mean()
    gain_m12 = (p("mean_12") - p(ship)) / p("mean_12") * 100
    gain_b = (p("mean_12", fold="B") - p(ship, fold="B")) / p("mean_12", fold="B") * 100
    lo, hi = config.TIER_THRESHOLDS_PCT

    split_rows = [[f, info["folds"][f]["train_targets"], str(info["folds"][f]["n_train"]),
                   info["folds"][f]["test_targets"], str(info["folds"][f]["n_test"])] for f in sorted(config.FOLDS)]
    iv_rows = [[x["target"], candidates.LABEL[x["method"]], f"{x['q_low']:.3f} .. {x['q_high']:.3f}",
                fmt(x["coverage_pooled_in_sample"] * 100) + "%", fmt(x["coverage_fold_A_ratios_on_B"] * 100) + "%",
                fmt(x["coverage_rf_tree_spread_pooled"] * 100) + "%"] for x in ivals]
    ref_rows = [[candidates.LABEL[k], fmt(v), fmt(p(k, t=ic))] for k, v in REFERENCE_NUMBERS_IC.items()]
    sel_rows = [[candidates.LABEL[r["method"]], fmt(r["mae_B"]), f"{r['gain_B_pct']:+.1f}%", fmt(r["mae_pooled"]),
                 f"{r['gain_pooled_pct']:+.1f}%", "yes" if r["qualifies"] else "no"] for r in decision["selection_table"]]
    tier_methods = ["mean_12", "poisson_glm", "random_forest", "blend", "glm_extended", "stacked_blend"]
    seasonal_line = ("" if config.TIER_REFERENCE != "seasonal" else
                     " Part of this skill is regression to the mean: one month is a noisy reference, so when last "
                     "year's month was unusually high both the forecast and the outcome tend to land below it. It is "
                     "a real, checkable pattern, not an explanation of why activity changes.")
    shipped_is_ref = ship == ref
    grid = decision["tier_grid"]

    def best_skill(reference: str) -> str:
        g = grid[grid["reference"] == reference].sort_values("skill", ascending=False).iloc[0]
        return f"{g['skill']:+.3f} (window {int(g['window'])}, {g['thresholds']}%)"

    gain_a = (p("mean_12", fold="A") - p(ship, fold="A")) / p("mean_12", fold="A") * 100
    m12_beats_all_b = all(p("mean_12", fold="B") <= p(x, fold="B") for x in METHOD_ORDER
                          if x not in ("mean_12",) and not np.isnan(p(x, fold="B")))
    floor_share = min(floor["incident_count"] / p(ship, t=ic), floor["weighted_index"] / p(ship)) * 100

    md = f"""# NeighbourCast: how accurate is the forecast?

Generated by `ml/src/evaluate.py` (with `ml/src/study.py`) from `{config.PROCESSED_CSV}`, data through
{config.DATA_THROUGH}. Every number is reported incidents, or their severity-weighted index, per neighbourhood per
month; nothing here rates any place.

## Headline

- **What is forecast.** For each of Vancouver's 24 VPD neighbourhoods, the {common.month_name(config.FORECAST_MONTH)}
  level of reported-incident activity, {config.HORIZON_MONTHS} months ahead of the last complete month
  ({common.month_name(config.DATA_THROUGH)}; September 2026 is only partly published). The main number is a
  severity-weighted index (each incident type weighted by Statistics Canada's Crime Severity Index weight); the
  plain count of reported incidents comes from the same model.
- **How far off it is.** Tested on 20 months it had not seen (2025-01..2026-08), the forecast missed by
  **{fmt(p(ship, t=ic))} reported incidents** per neighbourhood-month on average (the average month had
  {fmt(avg_actual_ic, 0)}), or {fmt(p(ship))} index points (average {fmt(avg_actual_wi, 0)}): a typical miss of
  **{fmt(p(ship, 'wape_pct'), 0)}%** of the actual value.
- **Compared with a simple average.** Just repeating each area's 12-month average misses by {fmt(p('mean_12', t=ic))}
  incidents ({fmt(p('mean_12'))} index points). The model is **{fmt(gain_m12)}% {"better" if gain_m12 >= 0 else "worse"} overall**,
  {"better" if gain_a >= 0 else "worse"} in 2025 ({fmt(gain_a)}%) and {"worse" if gain_b < 0 else "better"} in 2026
  ({fmt(p(ship, fold='B'))} vs {fmt(p('mean_12', fold='B'))} index points). That is a small edge: by our estimate
  {fmt(floor_share, 0)}% or more of the remaining error is month-to-month randomness no model can remove (see Limitations).
- **What the range covers.** The {int(config.INTERVAL_LEVEL * 100)}% range around each forecast is built from past
  forecast errors. Built from 2025 errors only, it contained the real 2026 value **{fmt(iv['coverage_fold_A_ratios_on_B'] * 100, 0)}%**
  of the time (target {int(config.INTERVAL_LEVEL * 100)}%). It is wide: roughly {fmt(iv['q_low'] * 100 - 100, 0)}% to
  +{fmt(iv['q_high'] * 100 - 100, 0)}% around the forecast.
- **The map colour (tier).** Each area is coloured by comparing the forecast with its own history: {tier_phrase()}.
  On the test months the forecast's colour matched the realised colour **{fmt(p(ship, 'tier_accuracy') * 100, 0)}%** of the
  time, against {fmt(p(ship, 'tier_majority_baseline') * 100, 0)}% for always guessing the most common colour.

## Decision rules (fixed before the results)

1. **Model.** Pre-registered on 2026-10-04 before the candidates were run (`reports/model_study.md`): a new
   candidate replaces the 2026-10-03 Poisson GLM (C0) only if its weighted_index MAE is at least
   {config.SELECTION_MIN_FOLD_B_GAIN_PCT:g}% lower on fold B (2026, the most recent months) AND lower pooled over both folds;
   among qualifiers the lowest pooled MAE ships, a simpler one within {config.SELECTION_TIE_PCT:g}% wins ties.
   Everything tuned (feature variant, blend weights, per-area factors) was tuned on fold A only.
2. **Tier.** Grid of window {{12, 24, 36}} months x thresholds {{+-5, +-8, +-10}}% x reference {{trailing mean,
   same-calendar-month mean}}; maximise macro-F1 minus the always-guess-the-most-common-tier accuracy, subject to a
   readable map (at least 3 areas below and 3 above in the 2026-10 forecast) and 30-60% of history months
   `typical`. The same rule (`ml/src/tiers.py`) labels history, backtest and forecast.
3. **Range.** {int(config.INTERVAL_LEVEL * 100)}% range = forecast x the 10th and 90th percentiles of actual / forecast over the
   backtest, pooled across areas (not Random Forest tree spread, which under-covers).

## Setup

- Target month = origin month + {config.HORIZON_MONTHS}. Features use months up to the origin only; 2026-09 (partial) is
  never a feature or a target. Expanding window split by target month; training targets from {config.TRAIN_START}.
- Every method is scored on identical rows ({info['n_pooled']} per target pooled).

{md_table(["fold", "train target months", "train rows", "test target months", "test rows"], split_rows)}

## Model decision

{md_table(["candidate (weighted_index)", "MAE fold B", "vs C0 on B", "MAE pooled", "vs C0 pooled", "qualifies"], sel_rows)}

C0 (`{ref}`): fold B {fmt(p(ref, fold='B'))}, pooled {fmt(p(ref))}. 12-month mean: fold B {fmt(p('mean_12', fold='B'))},
pooled {fmt(p('mean_12'))}.

**Shipped: `{ship}`** ({decision['selection_reason']}). {"None of the five new candidates beat the existing GLM by the margin the rule requires, so nothing changed in the model. That is the honest result: per-type models, extra features, gradient boosting, stacking and per-area correction did not reduce the error on unseen months." if shipped_is_ref else ""}
Gain vs the 12-month mean: {fmt(gain_m12)}% ({fmt(p('mean_12') - p(ship))} index points pooled).
Gain vs the previous GLM: {fmt((p(ref) - p(ship)) / p(ref) * 100)}%.
Full candidate details, fold-A choices and month-by-month comparisons: `reports/model_study.md`.

## Results: weighted_index (decision target)

{study.results_table(mt, wi, decision)}

"months beating C0" = test months (of 20; of 8 for C5) whose total absolute error over the 24 areas is lower than C0's.

## Results: incident_count

{study.results_table(mt, ic, decision)}

Reproducibility check against the independent benchmark of 2026-10-03 (incident_count, pooled MAE):

{md_table(["method", "benchmark", "this run"], ref_rows)}

## Tier decision

Rule: {tier_phrase()}. Areas averaging fewer than {config.TIER_MIN_MEAN} reported incidents a month
(Musqueam) are `insufficient_data`.

Why this choice: the team's earlier settings compared each month with a trailing average (36 months, then 12).
"Skill" below is macro-F1 minus the accuracy of always guessing the most common tier (above 0 = better than the
trivial guess). The best trailing-average setting scored {best_skill('trailing_mean')}; the best same-calendar-month
setting scored {best_skill('seasonal')}. A trailing average ignores the season, so the realised tier mostly tracks
the calendar and the forecast's tier adds little; comparing with the same calendar month leaves a tier the forecast
can anticipate. The chosen setting: macro-F1 {fmt(tc.get('tier_macro_f1', np.nan), 3)}, accuracy
{fmt(tc.get('tier_accuracy', np.nan) * 100 if tc else np.nan)}% vs {fmt(tc.get('tier_majority_baseline', np.nan) * 100 if tc else np.nan)}% for
always guessing the most common tier.{seasonal_line} It gives a readable 2026-10 map and keeps
{fmt(tc.get('history_share_typical', np.nan) * 100 if tc else np.nan, 0)}% of history months `typical`.
{"**No cell met both pre-registered constraints**; the pick keeps the readable-map constraint and misses the 30-60% `typical` history share (fallback rule stated in `reports/model_study.md`; added after seeing the grid)." if tc.get('choice_basis', '').startswith('fallback') else ""}
The full 18-cell grid is in `reports/model_study.md` and `ml/outputs/tier_study_results.csv`.

Honest reading: with this reference the plain 12-month mean gets the tier right {fmt(p('mean_12', 'tier_accuracy') * 100)}% of the
time vs {fmt(p(ship, 'tier_accuracy') * 100)}% for the shipped model, so the tier's skill comes from choosing a sensible
reference, not from the model. Because the reference is a single month, an area whose month a year earlier was
unusually quiet or busy can show a large `pct_vs_typical` (each forecast record carries `typical_weighted_index`, the
level it is compared with, so the app can show it).

Tier metrics on the pooled test rows (weighted_index):

{tier_table(m, wi, tier_methods)}

## Uncertainty ranges ({int(config.INTERVAL_LEVEL * 100)}% nominal)

Ratio actual / forecast pooled across areas and both folds; its Q10 and Q90 multiply the forecast (forecasts under
{intervals.MIN_FORECAST_FOR_RATIO:g} are left out of the ratios). In-sample coverage is ~{int(config.INTERVAL_LEVEL * 100)}% by construction;
**fold A ratios applied to fold B** is the honest out-of-sample check. Random Forest tree spread is for comparison only.

{md_table(["target", "method", "ratio Q-low .. Q-high", "coverage, pooled ratios (in-sample)",
           "coverage, fold A ratios on fold B", "coverage, RF tree spread"], iv_rows)}

## Forecast tier distribution

{FORECAST_SECTION_START}
_Filled in by `ml/src/forecast.py`._
{FORECAST_SECTION_END}

## Limitations

- **Noise floor.** Monthly counts are random even when nothing changes. For the median neighbourhood
  ({noise['median_area']}, about {noise['median_area_incidents']:.0f} reported incidents a month) Poisson noise alone is
  about **{noise['incident_count_pct']:.0f}% of a month's count** and {noise['weighted_index_pct']:.0f}% of its weighted index
  (computed from the last 12 months of data). A forecast that knew every area's true monthly mean would still miss by
  about {fmt(floor['incident_count'])} incidents ({fmt(floor['weighted_index'])} index points) on these test rows:
  **{fmt(floor['incident_count'] / p(ship, t=ic) * 100, 0)}% of the current error on counts and
  {fmt(floor['weighted_index'] / p(ship) * 100, 0)}% on the index is irreducible** under that (optimistic) model. Real counts are
  over-dispersed (clustered events, duplicated records), so the true share is likely higher. Better models can only work on the remainder.
- Two test periods ({", ".join(f"{a}..{b}" for a, b in config.FOLDS.values())}), 20 months in all, are a small sample; MAE
  differences of a few percent between methods are not reliable (see the month-by-month sign counts).
- {"In 2026 (fold B) the 12-month mean beat every model" if m12_beats_all_b else "Results differ between 2025 and 2026"}; a different test year could reverse the overall ranking.
- Offence Against a Person has a reporting lag, so the most recent months are under-reported.
- Category mix shifts over time (Theft from Vehicle down, Other Theft up), so the weighted index and the count can
  move differently.
- The index is CSI-inspired, not Statistics Canada's Crime Severity Index: 8 VPD types, 2009 published weights, no
  population denominator (see `ml/README.md`, "Severity weights").

## What changed on 2026-10-04

- **Config typo fixed:** `FORECAST_MONTH` was "2026-010"; now "{config.FORECAST_MONTH}".
- **Severity weights cited and set to the published values:** Statistics Canada 85-004-X (2009) Table 1
  (Theft under $5,000 37, Mischief 30, Assault level 2 77, Breaking and entering 187, Theft of a motor vehicle 84).
  The previous working values were the same weights x ~0.79, so relative weights barely moved; the index scale rose
  by about 27% (pooled C0 MAE 559.9 -> {fmt(p(ref))}) while the count results are unchanged.
- **Model study** (pre-registered): 5 new candidates tried on identical rows; result: shipped model `{ship}`.
- **Tiers made consistent and meaningful:** a teammate had set the window to 12 months and regenerated only the
  forecast, so history (36 months) and forecast (12) disagreed. History, backtest and forecast are now all produced by
  `tiers.py` with one setting: window {config.TIER_WINDOW_MONTHS}, thresholds {lo:+g}/{hi:+g}%, reference `{config.TIER_REFERENCE}`.
- Everything (features, history, evaluation, forecast, `ml/outputs/meta.json`) regenerated in one run.
"""
    path.write_text(md, encoding="utf-8")


# --------------------------------------------------------------------------- main
def main() -> None:
    t0 = time.time()
    features = load_features()
    monthly = common.load_monthly()
    print("Backtesting all methods and running the model / tier studies ...")
    bt, decision = study.run_all(features, monthly)
    shipped = decision["shipped_model"]

    metrics_df = all_metrics(bt)
    ivals = interval_summary(bt, shipped) + (interval_summary(bt, "random_forest") if shipped != "random_forest" else [])

    folds_info = {}
    for fold in sorted(config.FOLDS):
        train, test = candidates.train_test_split(features, fold)
        folds_info[fold] = {
            "train_targets": f"{train['target_month'].min()}..{train['target_month'].max()}",
            "test_targets": f"{test['target_month'].min()}..{test['target_month'].max()}",
            "n_train": int(len(train)), "n_test": int(len(test)),
        }
    info = {
        "decision_metric": config.DECISION_METRIC,
        "shipped_model": shipped,
        "glm_variant": "poisson_glm",
        "selection_reason": decision["selection_reason"],
        "reference_model": config.REFERENCE_MODEL,
        "mae_pooled_weighted_index": {k: candidates.fold_mae(bt, "weighted_index", "pooled", k)
                                      for k in METHOD_ORDER if k != "area_corrected"},
        "mae_fold_B_weighted_index": {k: candidates.fold_mae(bt, "weighted_index", "B", k) for k in METHOD_ORDER},
        "folds": folds_info,
        "n_pooled": int((bt.target == "weighted_index").sum()),
        "train_start": config.TRAIN_START,
        "horizon_months": config.HORIZON_MONTHS,
        "data_through": config.DATA_THROUGH,
        "model_description": MODEL_DESCRIPTIONS.get(shipped, shipped),
        # Everything forecast.py needs to refit any candidate exactly as it was backtested.
        "c2_variant": decision["c2_variant"],
        "stack_weights": decision["stack_weights"],
        "area_correction_parent": decision["area_correction_parent"],
        "area_factors": decision["area_factors"],
        "tier_choice": decision["tier_choice"],
        "noise_floor_mae": decision["noise_floor_mae"],
        "typical_area_noise": decision["typical_area_noise"],
    }

    cols = ["target", "fold", config.AREA_KEY, "origin_month", "target_month", "actual", "typical_mean",
            "area_mean_incidents"] + METHOD_ORDER + ["glm_extended_noTM", "glm_extended_TM", "rf_tree_low", "rf_tree_high"]
    bt[cols].round(4).to_csv(common.OUTPUTS / "backtest_predictions.csv", index=False)
    metrics_df.round(4).to_csv(common.OUTPUTS / "evaluation_metrics.csv", index=False)
    payload = {"decision": info, "intervals": ivals, "metrics": metrics_df.to_dict(orient="records")}
    (common.OUTPUTS / "evaluation.json").write_text(json.dumps(study.round_floats(payload), indent=2), encoding="utf-8")
    write_report(metrics_df, bt, info, ivals, decision, common.REPORTS / "evaluation.md")

    print("\nPooled MAE:")
    for target in config.TARGETS:
        row = {k: round(metric(metrics_df, target, "pooled", k, "mae"), 1) for k in METHOD_ORDER if k != "area_corrected"}
        print(f"  {target:15s} {row}")
    print(f"\nShipped model: {shipped} ({decision['selection_reason']})")
    print(f"Tier choice: {decision['tier_choice']}")
    for iv in ivals:
        print(f"  interval {iv['target']:15s} {iv['method']:17s} ratios {iv['q_low']:.3f}..{iv['q_high']:.3f}  "
              f"coverage in-sample {iv['coverage_pooled_in_sample']:.1%}, A->B {iv['coverage_fold_A_ratios_on_B']:.1%}")
    print(f"evaluate.py done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
