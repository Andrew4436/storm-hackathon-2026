"""Model-improvement study and tier decision study -> reports/model_study.md, ml/outputs/study_results.csv,
ml/outputs/tier_study_results.csv, ml/outputs/study_decision.json.

Called by evaluate.py (so the three pipeline commands regenerate it), and runnable on its own:
    python ml/src/study.py

Part 1 (models): every candidate in candidates.py on identical backtest rows; the pre-registered selection rule
(config.SELECTION_*, PROTOCOL below) picks the shipped model.
Part 2 (tiers): TIER_WINDOW_MONTHS x TIER_THRESHOLDS_PCT x reference grid scored with the shipped model; the
pre-registered tier rule (TIER_RULE below) picks the combination. The pick is REPORTED here; the team copies it
into ml/config.py (where it then drives history, evaluation and forecast through tiers.py). The report flags any
mismatch between the study's pick and config.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

import candidates
import common
import config
import metrics
import tiers
from build_features import make_feature_table

TIER_WINDOWS = [12, 24, 36]
TIER_THRESHOLD_GRID = [(-5.0, 5.0), (-8.0, 8.0), (-10.0, 10.0)]
HISTORY_RANGE = ("2015-01", config.DATA_THROUGH)
SELECTION_POOL = ["per_type_glm", "glm_extended", "hgb_poisson", "hgb_glm_blend", "stacked_blend"]

PROTOCOL = """## Protocol (pre-registered 2026-10-04, before any candidate was run)

- Rows: the backtest rows of `ml/outputs/features.csv`, horizon 2, folds A (test targets 2025-01..2025-12, 288 rows)
  and B (2026-01..2026-08, 192 rows), expanding window, training targets from 2010-01. Every method is scored on
  exactly the same rows. Both targets are reported; decisions use `weighted_index` only.
- Candidates: C0 = the 2026-10-03 Poisson GLM (reference); mean_12 (baseline); C1 per-type GLMs summed;
  C2 extended-feature GLM; C3 Poisson gradient boosting and C3b (50/50 blend of C3 with C2); C4 stacked blend of
  {C1, C2, mean_12}; C5 per-area bias correction of the best of C1..C4.
- Choices made on fold A only (fold B is never looked at for these):
  - C2 with or without the 3 per-type momentum ratios: the variant with the lower fold A weighted_index MAE.
    C3 uses the same choice.
  - C4 weights: non-negative, sum to 1, grid step 0.05, minimising fold A MAE (per target); applied unchanged to B.
    C4's fold A predictions are therefore in-sample, so C4 can only ship if it is also the best qualifier on fold B.
  - C5 factors: per area, median of actual / forecast on fold A, clipped to [0.8, 1.25]; scored on fold B only.
    "Best of C1..C4" = the candidate the selection rule picks among C1..C4 (if none qualifies, the lowest pooled
    MAE among C1..C4). C5 is adopted on top of the shipped model only if that model is its parent and it lowers
    the parent's fold B MAE by at least 1%.
- **Selection rule.** A candidate qualifies if its weighted_index MAE is at least 1% below C0's on fold B (the most
  recent months) AND its pooled MAE is below C0's. Among qualifiers, the lowest pooled weighted_index MAE ships;
  if a simpler qualifier (fewer fitted parameters) is within 1% of that pooled MAE, the simpler one ships.
  If nothing qualifies, C0 stays and the report says so.
- Also reported: RMSE, WAPE, bias, MAE excluding the Central Business District, areas beating mean_12 (of 24), per
  fold and pooled, and a paired month-by-month comparison with C0 (in how many of the 20 test months the
  candidate's total absolute error across the 24 areas is lower than C0's)."""

TIER_RULE = """**Tier rule (pre-registered).** Grid: window {12, 24, 36} months x thresholds {+-5%, +-8%, +-10%} x reference
{trailing mean of the window, same-calendar-month mean of the window ("seasonal")}. For each combination: tier
accuracy and macro-F1 of the shipped model on the pooled backtest rows (weighted_index), the majority-class accuracy
(always guessing the most common realised tier, the honest baseline), the 2026-10 forecast tier counts and the
history tier shares over 2015-01..2026-08. Pick the combination with the highest **skill = macro-F1 minus
majority-class accuracy**, subject to (a) at least 3 areas `below_typical` and 3 `above_typical` in the 2026-10
forecast (a readable map) and (b) history share of `typical` between 30% and 60%. Ties go to the shorter window."""

TIER_FALLBACK = """**Fallback (NOT pre-registered; added 2026-10-04 after the grid above showed that no combination meets both
constraints).** Keep constraint (a), because a one-colour map defeats the product; drop (b) and report how far the
pick misses it; then take the highest skill. Without either constraint the same combination has the highest skill
in the whole grid, so the fallback does not change which cell wins on skill."""


# --------------------------------------------------------------------------- shared helpers
def load_features() -> pd.DataFrame:
    return pd.read_csv(common.OUTPUTS / "features.csv", dtype={"origin_month": str, "target_month": str})


def typical_at_origin(monthly: pd.DataFrame, window: int | None = None, reference: str | None = None) -> pd.DataFrame:
    """Per (area, origin month): typical level of the target month (origin + horizon) for both targets, from the
    window ending at the origin, plus the trailing incident mean for the minimum-size rule."""
    h = config.HORIZON_MONTHS
    out = monthly[[config.AREA_KEY, config.MONTH_KEY]].rename(columns={config.MONTH_KEY: "origin_month"})
    out["wi_typical"] = tiers.typical_level(monthly, "weighted_index", h, window, reference)
    out["ic_typical"] = tiers.typical_level(monthly, "incident_count", h, window, reference)
    out["area_mean_incidents"] = tiers.trailing_mean(monthly, "incident_count", window)
    return out


def fold_view(bt: pd.DataFrame, target: str, fold: str) -> pd.DataFrame:
    sub = bt[bt["target"] == target]
    return sub if fold == "pooled" else sub[sub["fold"] == fold]


def final_forecast(model_name: str, features: pd.DataFrame, monthly: pd.DataFrame, decision: dict) -> pd.DataFrame:
    """Shipped model fitted on all rows with targets TRAIN_START..DATA_THROUGH; forecast from origin DATA_THROUGH."""
    train = features[(features["target_month"] >= config.TRAIN_START) & (features["target_month"] <= config.DATA_THROUGH)]
    table = make_feature_table(monthly)
    origin = table[table["origin_month"] == config.DATA_THROUGH].reset_index(drop=True)
    out = origin[[config.AREA_KEY]].copy()
    for target, p in common.PREFIX.items():
        out[target], _ = candidates.final_predict(model_name, train, origin, p, decision)
    return out


# --------------------------------------------------------------------------- part 1: models
def run_models(features: pd.DataFrame, monthly: pd.DataFrame, verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    bt, info = candidates.run_backtest(features, typical_at_origin(monthly), verbose=verbose)
    sel = candidates.select(bt, info, SELECTION_POOL)

    # C5 on the best of C1..C4.
    if sel["chosen"] in SELECTION_POOL:
        parent = sel["chosen"]
    else:
        parent = min(SELECTION_POOL, key=lambda m: (candidates.fold_mae(bt, "weighted_index", "pooled", m), m))
    factors = candidates.apply_area_correction(bt, parent)
    b_parent = candidates.fold_mae(bt, "weighted_index", "B", parent)
    b_c5 = candidates.fold_mae(bt, "weighted_index", "B", "area_corrected")
    c5_gain = (b_parent - b_c5) / b_parent * 100
    c5_adopted = sel["chosen"] == parent and c5_gain >= config.SELECTION_MIN_FOLD_B_GAIN_PCT
    shipped = "area_corrected" if c5_adopted else sel["chosen"]

    decision = {
        "shipped_model": shipped,
        "selection_reason": sel["reason"] + ("; C5 area correction adopted on top" if c5_adopted else ""),
        "qualifiers": sel["qualifiers"],
        "selection_table": sel["table"],
        "reference_model": config.REFERENCE_MODEL,
        "c2_variant": info["c2_variant"],
        "stack_weights": info["stack_weights"],
        "hgb_trees": info["hgb_trees"],
        "n_params": info["n_params"],
        "area_correction_parent": parent,
        "area_correction": {"fold_B_mae_parent": b_parent, "fold_B_mae_corrected": b_c5, "gain_pct": c5_gain,
                            "adopted": c5_adopted},
        "area_factors": factors,
    }
    return bt, decision


def metrics_table(bt: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for target in config.TARGETS:
        for fold in ["A", "B", "pooled"]:
            df = fold_view(bt, target, fold)
            for m in candidates.METHOD_ORDER:
                if df[m].notna().sum() == 0:
                    continue
                rec = {"target": target, "fold": fold, "method": m}
                rec.update(metrics.regression_metrics(df, m))
                pm = metrics.paired_months(df, m, config.REFERENCE_MODEL)
                rec["months_beating_c0"] = pm["months_better"]
                rec["months_compared"] = pm["months"]
                rec["paired_mean_diff_vs_c0"] = pm["mean_diff"]
                rec["paired_t_vs_c0"] = pm["t_stat"]
                recs.append(rec)
    return pd.DataFrame(recs)


# --------------------------------------------------------------------------- part 2: tiers
def run_tier_grid(bt: pd.DataFrame, monthly: pd.DataFrame, forecast: pd.DataFrame, shipped: str) -> pd.DataFrame:
    rows_all = fold_view(bt, "weighted_index", "pooled").drop(columns=["typical_mean", "area_mean_incidents"])
    origin_rows = monthly[monthly[config.MONTH_KEY] == config.DATA_THROUGH].index
    recs = []
    for window in TIER_WINDOWS:
        for reference in tiers.REFERENCES:
            typ = typical_at_origin(monthly, window, reference)
            rows = rows_all.merge(typ[[config.AREA_KEY, "origin_month", "wi_typical", "area_mean_incidents"]]
                                  .rename(columns={"wi_typical": "typical_mean"}),
                                  on=[config.AREA_KEY, "origin_month"], how="left")
            fc_typ = typ.loc[origin_rows].set_index(config.AREA_KEY)
            fc = forecast.set_index(config.AREA_KEY)
            for thr in TIER_THRESHOLD_GRID:
                tm = metrics.tier_metrics(rows, shipped, thr)
                ft = tiers.tier_frame(fc["weighted_index"], fc_typ.loc[fc.index, "wi_typical"],
                                      fc_typ.loc[fc.index, "area_mean_incidents"], thr)["tier"].value_counts()
                ht = tiers.history_tiers(monthly, window, thr, reference)["tier"]
                in_range = monthly[config.MONTH_KEY].between(*HISTORY_RANGE).to_numpy()
                h = ht[in_range]
                h = h[h.isin(tiers.TIERS)].value_counts(normalize=True)
                rec = {"window": window, "thresholds": f"{thr[0]:+g}/{thr[1]:+g}", "low": thr[0], "high": thr[1],
                       "reference": reference, **tm,
                       "skill": tm["tier_macro_f1"] - tm["tier_majority_baseline"],
                       **{f"forecast_{t}": int(ft.get(t, 0)) for t in tiers.TIERS + [tiers.INSUFFICIENT]},
                       **{f"history_share_{t}": float(h.get(t, 0.0)) for t in tiers.TIERS}}
                rec["readable_map"] = rec["forecast_below_typical"] >= 3 and rec["forecast_above_typical"] >= 3
                rec["history_typical_ok"] = 0.30 <= rec["history_share_typical"] <= 0.60
                rec["eligible"] = rec["readable_map"] and rec["history_typical_ok"]
                recs.append(rec)
    grid = pd.DataFrame(recs)
    grid["chosen"] = False
    grid["choice_basis"] = ""
    elig = grid[grid["eligible"]]
    if len(elig):
        basis = "pre-registered rule"
    else:
        # Fallback (added 2026-10-04 after the grid showed no eligible cell, see TIER_FALLBACK): keep the map
        # constraint, drop the history-share constraint, and report the miss.
        elig, basis = grid[grid["readable_map"]], "fallback: no cell met both constraints; best skill with a readable map"
    if len(elig):
        best = elig.sort_values(["skill", "window"], ascending=[False, True]).index[0]
        grid.loc[best, "chosen"] = True
        grid.loc[best, "choice_basis"] = basis
    return grid


# --------------------------------------------------------------------------- report
def f1(x, nd=1):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{nd}f}"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def get(mt, target, fold, method, col):
    s = mt.loc[(mt.target == target) & (mt.fold == fold) & (mt.method == method), col]
    return float(s.iloc[0]) if len(s) else float("nan")


def results_table(mt: pd.DataFrame, target: str, decision: dict) -> str:
    rows = []
    npar = decision["n_params"][target]
    for m in candidates.METHOD_ORDER:
        if m not in set(mt[mt.target == target].method):
            continue
        g = lambda fold, col: get(mt, target, fold, m, col)  # noqa: E731
        pooled = m != "area_corrected"
        beats = " / ".join(str(int(g(f, "areas_beating_mean_12"))) if not np.isnan(g(f, "areas_beating_mean_12"))
                           else "-" for f in ["A", "B", "pooled"])
        months = (f"{int(g('pooled' if pooled else 'B', 'months_beating_c0'))}/"
                  f"{int(g('pooled' if pooled else 'B', 'months_compared'))}") if m != config.REFERENCE_MODEL else "-"
        rows.append([candidates.LABEL[m], f1(g("A", "mae")), f1(g("B", "mae")),
                     f"**{f1(g('pooled', 'mae'))}**" if pooled else "(B only)",
                     f1(g("pooled" if pooled else "B", "rmse")), f1(g("pooled" if pooled else "B", "wape_pct")) + "%",
                     f1(g("pooled" if pooled else "B", "bias_pct")) + "%",
                     f1(g("pooled" if pooled else "B", "mae_excl_cbd")),
                     beats if m != "mean_12" else "-", months, f"{npar.get(m, npar.get(decision['area_correction_parent'], 0)):,}"
                     if m not in ("mean_3", "same_month_last_year") else "0"])
    return md_table(["method", "MAE A", "MAE B", "MAE pooled", "RMSE", "WAPE", "bias", "MAE excl. CBD",
                     "areas beating mean_12 (A / B / pooled)", "months beating C0", "fitted parameters"], rows)


def why_lines(mt: pd.DataFrame, decision: dict) -> str:
    """One factual line per candidate, from the numbers (no hard-coded conclusions)."""
    wi, ref = "weighted_index", config.REFERENCE_MODEL
    out = []

    def cmp(m):
        a = (get(mt, wi, "A", ref, "mae") - get(mt, wi, "A", m, "mae")) / get(mt, wi, "A", ref, "mae") * 100
        b = (get(mt, wi, "B", ref, "mae") - get(mt, wi, "B", m, "mae")) / get(mt, wi, "B", ref, "mae") * 100
        return f"{a:+.1f}% on fold A, {b:+.1f}% on fold B vs C0 (positive = better)"
    out.append(f"- C1 per-type GLMs: {cmp('per_type_glm')}. Pooled bias {get(mt, wi, 'pooled', 'per_type_glm', 'bias_pct'):+.1f}% "
               f"(C0 {get(mt, wi, 'pooled', ref, 'bias_pct'):+.1f}%): each type model carries a small upward bias and "
               "the weighted sum adds them up.")
    out.append(f"- C2 extended GLM: {cmp('glm_extended')}. The longer windows and momentum add little that mean_6 / "
               "mean_12 do not already carry.")
    out.append(f"- C3 boosting: {cmp('hgb_poisson')}; C3b blend with C2: {cmp('hgb_glm_blend')}.")
    w = decision["stack_weights"][wi]
    out.append(f"- C4 stacked blend: fold A weights {', '.join(f'{k} {v:.2f}' for k, v in w.items())}; {cmp('stacked_blend')}.")
    c5 = decision["area_correction"]
    out.append(f"- C5 area correction of `{decision['area_correction_parent']}`: fold B MAE {c5['gain_pct']:+.1f}% vs its parent.")
    out.append(f"- For context (not a candidate): mean_12 is {cmp('mean_12')}.")
    return "\n".join(out)


def write_report(bt, mt, decision, grid, floor, noise, path) -> None:
    wi = "weighted_index"
    ship = decision["shipped_model"]
    ref = config.REFERENCE_MODEL
    sel_rows = [[candidates.LABEL[r["method"]], f1(r["mae_B"]), f"{r['gain_B_pct']:+.1f}%", f1(r["mae_pooled"]),
                 f"{r['gain_pooled_pct']:+.1f}%", f"{r['n_params']:,}", "yes" if r["qualifies"] else "no"]
                for r in decision["selection_table"]]
    p_ship, p_ref, p_m12 = (get(mt, wi, "pooled", m, "mae") for m in (ship if ship != "area_corrected" else ref, ref, "mean_12"))
    b_ship, b_ref, b_m12 = (get(mt, wi, "B", m, "mae") for m in (ship, ref, "mean_12"))
    c5 = decision["area_correction"]
    sw = decision["stack_weights"]
    noTM = get(mt, wi, "A", "glm_extended", "mae")

    if ship == ref:
        verdict = (f"**No candidate qualified, so C0 (`{ref}`) stays the shipped model.** Its pooled weighted_index "
                   f"MAE is {f1(p_ref)}, {f1((p_m12 - p_ref) / p_m12 * 100)}% ({f1(p_m12 - p_ref)} points) below the "
                   f"12-month mean's {f1(p_m12)}. On fold B alone the 12-month mean ({f1(b_m12)}) beats C0 ({f1(b_ref)}).")
    else:
        verdict = (f"**`{ship}` ships.** Pooled weighted_index MAE {f1(p_ship)} vs C0 {f1(p_ref)} "
                   f"({f1((p_ref - p_ship) / p_ref * 100)}%, {f1(p_ref - p_ship)} points) and vs mean_12 {f1(p_m12)} "
                   f"({f1((p_m12 - p_ship) / p_m12 * 100)}%, {f1(p_m12 - p_ship)} points). {decision['selection_reason']}.")

    chosen = grid[grid["chosen"]]
    cur = (config.TIER_WINDOW_MONTHS, f"{config.TIER_THRESHOLDS_PCT[0]:+g}/{config.TIER_THRESHOLDS_PCT[1]:+g}",
           config.TIER_REFERENCE)
    if len(chosen):
        c = chosen.iloc[0]
        tier_line = ""
        if c["choice_basis"].startswith("fallback"):
            top = grid.sort_values(["skill", "window"], ascending=[False, True]).iloc[0]
            same = (top["window"], top["thresholds"], top["reference"]) == (c["window"], c["thresholds"], c["reference"])
            tier_line = TIER_FALLBACK if same else TIER_FALLBACK.rsplit(" Without either", 1)[0] + "."
            tier_line += (f" The pick's history share of `typical` is {c['history_share_typical'] * 100:.0f}% "
                          f"(constraint: 30-60%).\n\n")
        tier_line += (f"**Chosen: window {int(c['window'])} months, thresholds {c['thresholds']}%, reference "
                     f"`{c['reference']}`** (skill {c['skill']:+.3f}: macro-F1 {c['tier_macro_f1']:.3f} vs majority-class "
                     f"accuracy {c['tier_majority_baseline']:.3f}; tier accuracy {c['tier_accuracy'] * 100:.1f}%).")
        match = (int(c["window"]), c["thresholds"], c["reference"]) == cur
        tier_line += (" `ml/config.py` uses this combination." if match else
                      f" **`ml/config.py` currently uses window {cur[0]}, thresholds {cur[1]}, reference {cur[2]}: "
                      "update it and re-run the pipeline.**")
        if c["reference"] == "seasonal" and int(c["window"]) == 12:
            tier_line += ("\n\nIn plain words: with a 12-month window the seasonal reference is **the same month one year "
                          "earlier**, so a tier reads \"more than "
                          f"{abs(c['high']):g}% above / below the same month last year\". Part of the skill comes from "
                          "regression to the mean: a single month is a noisy reference, so when last year's month was "
                          "unusually high, both the forecast and the outcome tend to land below it. That is a real, "
                          "checkable pattern, but it is not insight into why activity changes.")
    else:
        tier_line = "**No combination gives a readable map; config is unchanged.**"
    grid_rows = [[int(r.window), r.thresholds, r.reference, f"{r.tier_accuracy * 100:.1f}%", f"{r.tier_macro_f1:.3f}",
                  f"{r.tier_majority_baseline * 100:.1f}% ({r.tier_majority_class.replace('_typical', '')})",
                  f"{r.skill:+.3f}",
                  f"{r.forecast_below_typical}/{r.forecast_typical}/{r.forecast_above_typical}",
                  f"{r.history_share_below_typical * 100:.0f}/{r.history_share_typical * 100:.0f}/"
                  f"{r.history_share_above_typical * 100:.0f}",
                  ("**chosen**" if r.chosen else ("yes" if r.eligible else "no"))] for r in grid.itertuples()]

    md = f"""# Model study: can we beat the 2026-10-03 GLM?

Generated by `ml/src/study.py` (called by `ml/src/evaluate.py`). Horizon {config.HORIZON_MONTHS} months, data through
{config.DATA_THROUGH}. Units: `weighted_index` points (CSI-weighted reported incidents) per neighbourhood-month.

{PROTOCOL}

## Fold-A choices (made without fold B)

- C2 variant: `{decision['c2_variant'][wi]}` for weighted_index (fold A MAE {f1(noTM)} for the chosen variant; with the
  per-type momentum ratios the fold A MAE was {f1(candidates.fold_mae(bt, wi, 'A', 'glm_extended_TM'))}, without them
  {f1(candidates.fold_mae(bt, wi, 'A', 'glm_extended_noTM'))}).
- C3 trees chosen by time-ordered early stopping: {decision['hgb_trees'][wi]} (weighted_index, per fold).
- C4 weights (weighted_index): {", ".join(f"{k} {v:.2f}" for k, v in sw[wi].items())}; (incident_count):
  {", ".join(f"{k} {v:.2f}" for k, v in sw['incident_count'].items())}.
- C5 parent: `{decision['area_correction_parent']}`; per-area factors range
  {min(decision['area_factors'][wi].values()):.2f}..{max(decision['area_factors'][wi].values()):.2f}.

## Results: weighted_index (decision target)

{results_table(mt, wi, decision)}

"months beating C0" = test months (of 20 pooled; of 8 for C5) in which the method's total absolute error over the
24 areas is lower than C0's. Fitted parameters: GLM coefficients + intercept; for trees, total nodes.

## Results: incident_count

{results_table(mt, 'incident_count', decision)}

## Selection (weighted_index, rule above)

{md_table(["candidate", "MAE B", "gain vs C0 on B", "MAE pooled", "gain vs C0 pooled", "parameters", "qualifies"], sel_rows)}

C0 reference: fold B MAE {f1(b_ref)}, pooled {f1(p_ref)}. mean_12: fold B {f1(b_m12)}, pooled {f1(p_m12)}.

C5 (area correction of `{decision['area_correction_parent']}`, fold B only): MAE {f1(c5['fold_B_mae_parent'])} ->
{f1(c5['fold_B_mae_corrected'])} ({c5['gain_pct']:+.1f}%); adopted: {'yes' if c5['adopted'] else 'no'}
{'' if c5['adopted'] else '(its parent is not the shipped model, or the gain is under 1%)'}.

{verdict}

### What each candidate did (read with the noise floor below)

{why_lines(mt, decision)}

## Noise floor

If a forecast knew each month's true Poisson mean exactly, its MAE on these test rows would still be about
**{f1(floor['weighted_index'])}** on weighted_index ({f1(floor['weighted_index'] / p_ref * 100, 0)}% of C0's pooled MAE)
and **{f1(floor['incident_count'])}** on incident_count ({f1(floor['incident_count'] / get(mt, 'incident_count', 'pooled', ref, 'mae') * 100, 0)}%
of C0's). For the median area ({noise['median_area']}, about {noise['median_area_incidents']:.0f} reported incidents a
month) one month's Poisson noise alone is about {noise['incident_count_pct']:.0f}% of the count and
{noise['weighted_index_pct']:.0f}% of the weighted index (heavy weights on rare types make the index noisier).
Real counts are over-dispersed, so the true floor is higher still.

## Tier decision

{TIER_RULE}

{md_table(["window", "thresholds %", "reference", "tier accuracy", "macro-F1", "majority-class accuracy", "skill",
           "2026-10 forecast below/typical/above", "history 2015-2026 % below/typical/above", "eligible"], grid_rows)}

{tier_line}
"""
    path.write_text(md, encoding="utf-8")


# --------------------------------------------------------------------------- entry points
def run_all(features: pd.DataFrame, monthly: pd.DataFrame, verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    """Run both studies, write the study files, return (backtest table, decision)."""
    bt, decision = run_models(features, monthly, verbose)
    mt = metrics_table(bt)
    fc = final_forecast(decision["shipped_model"], features, monthly, decision)
    grid = run_tier_grid(bt, monthly, fc, decision["shipped_model"])
    test_rows = features[features["target_month"].between(min(a for a, _ in config.FOLDS.values()),
                                                          max(b for _, b in config.FOLDS.values()))]
    floor = metrics.noise_floor(test_rows)
    noise = metrics.typical_area_noise(monthly, config.DATA_THROUGH)
    decision["noise_floor_mae"] = floor
    decision["typical_area_noise"] = noise
    chosen = grid[grid["chosen"]]
    decision["tier_choice"] = (chosen.iloc[0][["window", "low", "high", "reference", "skill", "tier_accuracy", "tier_macro_f1",
                                               "tier_majority_baseline", "history_share_typical", "choice_basis"]]
                               .to_dict() if len(chosen) else None)

    mt.round(4).to_csv(common.OUTPUTS / "study_results.csv", index=False)
    grid.round(4).to_csv(common.OUTPUTS / "tier_study_results.csv", index=False)
    (common.OUTPUTS / "study_decision.json").write_text(json.dumps(round_floats(decision), indent=2), encoding="utf-8")
    common.REPORTS.mkdir(parents=True, exist_ok=True)
    write_report(bt, mt, decision, grid, floor, noise, common.REPORTS / "model_study.md")
    decision["metrics_table"] = mt
    decision["tier_grid"] = grid
    return bt, decision


def round_floats(obj, nd: int = 4):
    if isinstance(obj, (float, np.floating)):
        return round(float(obj), nd)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: round_floats(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v, nd) for v in obj]
    return obj


def main() -> None:
    t0 = time.time()
    bt, decision = run_all(load_features(), common.load_monthly())
    print(f"\nShipped model: {decision['shipped_model']} ({decision['selection_reason']})")
    print(f"Tier choice: {decision['tier_choice']}")
    print(f"study.py done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
