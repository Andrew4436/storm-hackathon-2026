"""Step 2: backtest every method on identical rows -> metrics, backtest predictions, the model decision and the
judge-facing report.

Runs study.py's model and tier studies (so reports/model_study.md is regenerated with every run), then:
    ml/outputs/backtest_predictions.csv   one row per (target, fold, area, target month), one column per method
    ml/outputs/evaluation_metrics.csv     one row per (target, fold, method): regression + tier metrics
    ml/outputs/evaluation.json            decision, ranges, metrics, interval quantiles, noise floor, probability scores
    ml/outputs/probability_reliability.csv  reliability bins of the band probabilities (both targets, both directions)
    reports/evaluation.md                 plain-language report (forecast.py fills the forecast section)

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
import probabilities
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


# --------------------------------------------------------------------------- probabilities
PROB_DIRECTIONS = [("A", "B"), ("B", "A")]          # (fold the ratios come from, fold they are scored on)
PROB_SET_ORDER = ["chosen", "other", "climatology", "hard_tier", "point_tier"]
PROB_SET_LABEL = {
    "kde": "probabilities, Gaussian-kernel ratios",
    "lognormal": "probabilities, lognormal ratios",
    "climatology": "baseline: base rates of the ratio fold",
    "hard_tier": "baseline: hard tier (100% on the most likely)",
    "point_tier": "baseline: hard tier from the point forecast",
}
RELIABILITY_MIN_N = 10   # bins with fewer rows are not quoted in the plain-language statement


def fold_year(fold: str) -> str:
    return config.FOLDS[fold][0][:4]


def probability_sets(bt: pd.DataFrame, method: str, target: str, train_fold: str, test_fold: str):
    """Probability arrays for the scored rows of `test_fold`, with ratios / base rates from `train_fold` only.

    Scored rows: the realised month has a real tier (not insufficient_data / no reference), i.e. Musqueam is out.
    """
    tr, te = fold_view(bt, target, train_fold), fold_view(bt, target, test_fold)
    y_tr = probabilities.realised_outcome(tr["actual"], tr["typical_mean"], tr["area_mean_incidents"])
    y_te = probabilities.realised_outcome(te["actual"], te["typical_mean"], te["area_mean_incidents"])
    keep = (y_te >= 0) & probabilities.eligible(te["typical_mean"], te["area_mean_incidents"])
    te, y = te[keep], y_te[keep]
    sets = {}
    for pm in probabilities.METHODS:
        dist = probabilities.fit_distribution(tr["actual"], tr[method], pm)
        sets[pm] = probabilities.band_probabilities(te[method], te["typical_mean"], te["area_mean_incidents"], dist)
    base = np.bincount(y_tr[y_tr >= 0], minlength=3) / (y_tr >= 0).sum()
    sets["climatology"] = np.tile(base, (len(y), 1))
    point = probabilities.realised_outcome(te[method], te["typical_mean"], te["area_mean_incidents"])
    sets["point_tier"] = np.eye(3)[point]
    return sets, y, base


def calibration_statement(rel_above: list[dict], rel_below: list[dict], train_fold: str, test_fold: str) -> str:
    """Plain sentence from the highest well-populated bin of each event."""
    lo, hi = config.TIER_THRESHOLDS_PCT
    parts = []
    for rel, words in [(rel_above, f"more than {hi:g}% above its usual level"),
                       (rel_below, f"more than {abs(lo):g}% below it")]:
        cands = [r for r in rel if r["n"] >= RELIABILITY_MIN_N]
        r = max(cands, key=lambda r: r["predicted"])
        parts.append(f"when the forecast said {r['bin']} chance of a month {words}, it happened "
                     f"{r['observed'] * 100:.0f}% of the time ({r['n']} area-months)")
    return (f"Built from {fold_year(train_fold)} errors and checked on {fold_year(test_fold)}: "
            + "; ".join(parts) + ".")


def probabilistic_summary(bt: pd.DataFrame, method: str) -> dict:
    """Out-of-sample scoring of the band probabilities: ratios from one fold applied to the other, both targets.

    The smoothing (kde or lognormal) is chosen on weighted_index: lognormal if its Brier (above + below, summed over
    both directions) is at most the kernel's, else the kernel.
    """
    raw = {(t, a, b): probability_sets(bt, method, t, a, b) for t in config.TARGETS for a, b in PROB_DIRECTIONS}
    sc = {key: {pm: metrics.probability_scores(sets[pm], y) for pm in probabilities.METHODS}
          for key, (sets, y, _) in raw.items()}
    total = {pm: sum(sc[("weighted_index", a, b)][pm]["brier_above"] + sc[("weighted_index", a, b)][pm]["brier_below"]
                     for a, b in PROB_DIRECTIONS) for pm in probabilities.METHODS}
    chosen = "lognormal" if total["lognormal"] <= total["kde"] else "kde"
    other = "kde" if chosen == "lognormal" else "lognormal"

    scores, reliability_rows, rel = [], [], {}
    for (target, a, b), (sets, y, base) in raw.items():
        sets["hard_tier"] = np.eye(3)[np.argmax(sets[chosen], axis=1)]
        for name in PROB_SET_ORDER:
            key = {"chosen": chosen, "other": other}.get(name, name)
            rec = {"target": target, "ratios_from": a, "scored_on": b, "method": key, "role": name}
            rec.update(metrics.probability_scores(sets[key], y))
            scores.append(rec)
        for event, col, k in [("above", 2, 2), ("below", 0, 0)]:
            r = metrics.reliability(sets[chosen][:, col], (y == k).astype(float))
            rel[(target, a, b, event)] = r
            reliability_rows += [{"target": target, "ratios_from": a, "scored_on": b, "event": event, **x} for x in r]
        if target == "weighted_index" and (a, b) == PROB_DIRECTIONS[0]:
            base_rates = dict(zip(probabilities.OUTCOMES, base.tolist()))
            agreement = float(np.mean(np.argmax(sets[chosen], axis=1) == np.argmax(sets["point_tier"], axis=1)))
            within_stats = {"max_p_within": float(sets[chosen][:, 1].max()),
                            "share_most_likely_typical": float(np.mean(np.argmax(sets[chosen], axis=1) == 1)),
                            "share_realised_typical": float(np.mean(y == 1)),
                            "share_point_tier_typical": float(np.mean(np.argmax(sets["point_tier"], axis=1) == 1))}

    # Largest reliability gap (rows with at least RELIABILITY_MIN_N) on weighted_index, both directions.
    cands = [{**x, "event": ev, "direction": f"{fold_year(a)}->{fold_year(b)}"}
             for (t, a, b, ev), r in rel.items() if t == "weighted_index" for x in r if x["n"] >= RELIABILITY_MIN_N]
    worst = max(cands, key=lambda x: abs(x["predicted"] - x["observed"]))
    ns = [x["n"] for x in cands]
    worst["n_range"] = f"{min(ns)}-{max(ns)}"

    # The distributions the forecast uses: both folds pooled, exactly the pool of the 80% range.
    pooled = {}
    for target in config.TARGETS:
        v = fold_view(bt, target, "pooled")
        d = probabilities.fit_distribution(v["actual"], v[method], chosen)
        pooled[target] = {"n_ratios": d.n_ratios, "bandwidth": d.bandwidth, "mu": d.mu, "sigma": d.sigma,
                          "zero_share": d.zero_share, "description": probabilities.describe(d)}

    def score(target, a, b, role, col):
        return next(s[col] for s in scores if (s["target"], s["ratios_from"], s["scored_on"], s["role"])
                    == (target, a, b, role))

    a, b = PROB_DIRECTIONS[0]
    wi = "weighted_index"
    n_rows = next(s["n"] for s in scores if (s["target"], s["ratios_from"], s["role"]) == (wi, a, "chosen"))
    rnd = lambda r: [{"bin": x["bin"], "predicted": None if x["predicted"] is None else round(x["predicted"], 3),  # noqa: E731
                      "observed": None if x["observed"] is None else round(x["observed"], 3), "n": x["n"]} for x in r]
    headline = {
        "brier_above": round(score(wi, a, b, "chosen", "brier_above"), 4),
        "brier_below": round(score(wi, a, b, "chosen", "brier_below"), 4),
        "brier_above_baseline": round(score(wi, a, b, "climatology", "brier_above"), 4),
        "brier_below_baseline": round(score(wi, a, b, "climatology", "brier_below"), 4),
        "rps": round(score(wi, a, b, "chosen", "rps"), 4),
        "rps_baseline": round(score(wi, a, b, "climatology", "rps"), 4),
        "rps_hard_tier": round(score(wi, a, b, "hard_tier", "rps"), 4),
        "reliability_above": rnd(rel[(wi, a, b, "above")]),
        "reliability_below": rnd(rel[(wi, a, b, "below")]),
        "statement": calibration_statement(rel[(wi, a, b, "above")], rel[(wi, a, b, "below")], a, b),
        "scored_on": f"ratios from {fold_year(a)} applied to {fold_year(b)} ({n_rows} rows)",
    }
    comparison = (f"Brier above + below on weighted_index, summed over {fold_year('A')}->{fold_year('B')} and "
                  f"{fold_year('B')}->{fold_year('A')}: Gaussian kernel {total['kde']:.4f}, lognormal "
                  f"{total['lognormal']:.4f} -> {chosen} {'(calibrates at least as well)' if chosen == 'lognormal' else '(lower)'}.")
    return {"method": chosen, "method_comparison": comparison, "brier_sum_by_method": total,
            "pooled_distribution": pooled, "n_ratios_pooled": pooled["weighted_index"]["n_ratios"],
            "base_rates_fold_A": base_rates, "agreement_most_likely_vs_point_tier": agreement,
            "within_stats_fold_A_on_B": within_stats, "worst_bin": worst,
            "scores": scores, "reliability": reliability_rows, "reliability_by_key": rel, "headline": headline}


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


def pct(x) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def prob_score_table(prob: dict, target: str) -> str:
    rows = []
    for a, b in PROB_DIRECTIONS:
        for s in prob["scores"]:
            if (s["target"], s["ratios_from"], s["scored_on"]) != (target, a, b):
                continue
            label = PROB_SET_LABEL[s["method"]] + (" **(shipped)**" if s["role"] == "chosen" else "")
            rows.append([f"{fold_year(a)} -> {fold_year(b)}", label, str(s["n"]), f"{s['brier_above']:.4f}",
                         f"{s['brier_below']:.4f}", f"{s['rps']:.4f}", fmt(s["accuracy_most_likely"] * 100) + "%"])
    return md_table(["ratios from -> scored on", "probabilities", "rows", "Brier 'above'", "Brier 'below'", "RPS",
                     "most likely = realised"], rows)


def reliability_table(prob: dict, target: str, event: str) -> str:
    rel = prob["reliability_by_key"]
    (a1, b1), (a2, b2) = PROB_DIRECTIONS
    r1, r2 = rel[(target, a1, b1, event)], rel[(target, a2, b2, event)]
    rows = [[x["bin"], pct(x["predicted"]), pct(x["observed"]), str(x["n"]), pct(y["predicted"]), pct(y["observed"]),
             str(y["n"])] for x, y in zip(r1, r2)]
    h1, h2 = f"{fold_year(a1)}->{fold_year(b1)}", f"{fold_year(a2)}->{fold_year(b2)}"
    return md_table([f"predicted chance of '{event}'", f"{h1} mean predicted", f"{h1} happened", f"{h1} n",
                     f"{h2} mean predicted", f"{h2} happened", f"{h2} n"], rows)


def probability_section(prob: dict, iq_low: float, iq_high: float) -> str:
    lo, hi = config.TIER_THRESHOLDS_PCT
    h = prob["headline"]
    ws = prob["within_stats_fold_A_on_B"]
    wi, ic = "weighted_index", "incident_count"
    a, b = PROB_DIRECTIONS[0]
    get = lambda role, col, t=wi, d=PROB_DIRECTIONS[0]: next(  # noqa: E731
        s[col] for s in prob["scores"] if (s["target"], s["ratios_from"], s["scored_on"], s["role"]) == (t, *d, role))
    rps_skill = (1 - get("chosen", "rps") / get("climatology", "rps")) * 100
    rps_skill_2 = (1 - get("chosen", "rps", d=PROB_DIRECTIONS[1]) / get("climatology", "rps", d=PROB_DIRECTIONS[1])) * 100
    br = prob["base_rates_fold_A"]
    return f"""## Probabilities instead of tiers

**What the app shows now.** Instead of one label per area, three chances that add up to 100%: that the month's
severity-weighted index lands **more than {abs(lo):g}% below**, **within {lo:+g}/{hi:+g}%**, or **more than {hi:g}%
above** the area's usual level for that month (the same calendar month one year earlier, exactly the reference and
band the tiers used). Fields: `p_below`, `p_within`, `p_above` (3 decimals, summing to 1.000; null for
`insufficient_data`), `most_likely` (the largest of the three; `relative_activity_tier` now equals it, for
compatibility), and the same for reported-incident counts (`p_below_count`, `p_within_count`, `p_above_count`).
The map can colour by the continuous `pct_vs_typical` and show the chances on hover.

**How.** The point forecast F is combined with how far reality has landed from past forecasts: the ratios
actual / forecast of the shipped model's backtest (the same {prob['n_ratios_pooled']} points the {int(config.INTERVAL_LEVEL * 100)}%
range uses), smoothed into a continuous distribution. p_below is the chance that ratio x F falls under
usual x {1 + lo / 100:.2f}, p_above the chance it exceeds usual x {1 + hi / 100:.2f}. Code: `ml/src/probabilities.py`.

**Smoothing chosen: `{prob['method']}`.** {prob['method_comparison']}

**Scoring (out of sample).** The ratios come from one test year only and the probabilities are scored on the other
year; Musqueam (`insufficient_data`) is left out. Brier = mean squared gap between the chance given and what happened
(0/1); RPS (ranked probability score) does the same for the ordered three outcomes, so calling "below" when "above"
happened costs more than calling "within"; lower is better for both. Climatology = the base rates of the ratio year ({fold_year(a)}: below {br['below_typical'] * 100:.0f}%,
within {br['typical'] * 100:.0f}%, above {br['above_typical'] * 100:.0f}%) given to every area. Hard tier = 100% on the most likely outcome
(what a single label claims).

weighted_index (decision target):

{prob_score_table(prob, wi)}

Reading: the probabilities beat the base rates by {rps_skill:.0f}% on RPS ({fold_year(a)}->{fold_year(b)}) and {rps_skill_2:.0f}%
({fold_year(PROB_DIRECTIONS[1][0])}->{fold_year(PROB_DIRECTIONS[1][1])}), and beat both hard labels by a wider margin: the most-likely label is
wrong {(1 - get('hard_tier', 'accuracy_most_likely')) * 100:.0f}% of the time ({fold_year(a)}->{fold_year(b)}) and every miss costs the full penalty.
**Caveat on the label.** The band ({lo:+g}/{hi:+g}%) is narrow compared with the forecast error (80% range about
{(iq_low - 1) * 100:+.0f}%..{(iq_high - 1) * 100:+.0f}%), so the chance of landing within it peaks at
{ws['max_p_within'] * 100:.0f}% ({fold_year(a)}->{fold_year(b)}) and `typical` is the most likely outcome in
{ws['share_most_likely_typical'] * 100:.0f}% of rows (the old point-forecast tier said `typical` in
{ws['share_point_tier_typical'] * 100:.0f}%; {ws['share_realised_typical'] * 100:.0f}% of months really were). The most-likely label
therefore matches the old tier in only {prob['agreement_most_likely_vs_point_tier'] * 100:.0f}% of rows, yet matches the realised
outcome as often, because realised `typical` months are the minority. Show the three chances; the label is a coarse
summary.

**Reliability** (probabilities from the shipped smoothing, weighted_index). Each row groups the area-months by the
chance the forecast gave; "happened" is how often the event then occurred. Perfect calibration: the two match.

{reliability_table(prob, wi, "above")}

{reliability_table(prob, wi, "below")}

**In plain words:** {h['statement']} With {prob['worst_bin']['n_range']} area-months per row, gaps of about 10
points are within sampling noise. The largest gap in a row of at least {RELIABILITY_MIN_N}: '{prob['worst_bin']['event']}'
{prob['worst_bin']['bin']} ({prob['worst_bin']['direction']}), said {pct(prob['worst_bin']['predicted'])} on average, happened
{pct(prob['worst_bin']['observed'])} ({prob['worst_bin']['n']} area-months).

incident_count (secondary; same method, ratios from the count backtest):

{prob_score_table(prob, ic)}

{reliability_table(prob, ic, "above")}

{reliability_table(prob, ic, "below")}

All rows: `ml/outputs/probability_reliability.csv`; scores and settings: `ml/outputs/evaluation.json` (`probabilistic`).
"""


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


def write_report(m: pd.DataFrame, bt: pd.DataFrame, info: dict, ivals: list[dict], decision: dict, prob: dict,
                 path) -> None:
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
    prob_acc = [next(s["accuracy_most_likely"] for s in prob["scores"] if (s["target"], s["ratios_from"], s["scored_on"],
                                                                        s["role"]) == (wi, a, b, "chosen"))
                for a, b in PROB_DIRECTIONS]
    prob_dir = [f"{fold_year(a)}->{fold_year(b)}" for a, b in PROB_DIRECTIONS]

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
- **Chances, not a hard label.** Each area gets the chance that its month lands more than {abs(lo):g}% below, within
  {lo:+g}/{hi:+g}%, or more than {hi:g}% above its usual level (the same calendar month one year earlier). Scored on a year
  the chances were not built from, they beat simply quoting the base rates (RPS {prob['headline']['rps']:.3f} vs
  {prob['headline']['rps_baseline']:.3f}) and a hard label ({prob['headline']['rps_hard_tier']:.3f}). {prob['headline']['statement']}
- **Most-likely label (for reference).** The most likely of the three outcomes matched the realised one
  **{fmt(prob_acc[0] * 100, 0)}%** of the time ({prob_dir[0]}) and {fmt(prob_acc[1] * 100, 0)}% ({prob_dir[1]}); the old tier from
  the point forecast matched {fmt(p(ship, 'tier_accuracy') * 100, 0)}% on all test months, against
  {fmt(p(ship, 'tier_majority_baseline') * 100, 0)}% for always guessing the most common one.

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
4. **Probabilities.** Same reference and band as the tier; the chance of each outcome comes from the same backtest
   ratios, smoothed either by a Gaussian kernel on log-ratios (Scott's-rule bandwidth) or by a lognormal. The
   lognormal is used only if its out-of-sample Brier score (above + below, weighted_index, both fold directions) is
   at most the kernel's.

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

{probability_section(prob, iv['q_low'], iv['q_high'])}
## Most-likely tier (for reference)

The app no longer shows a hard tier on its own; `most_likely` (and `relative_activity_tier`, kept equal to it) is
the largest of the three probabilities above. This section documents how the reference level and the band were
chosen, and how the old point-forecast tier scored.

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

## Forecast probabilities and most-likely tiers

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
- **Probabilities instead of tiers** (team decision): the forecast now carries `p_below` / `p_within` / `p_above`
  (and `_count` versions) with the same reference and band; `relative_activity_tier` = `most_likely`, kept for
  compatibility. Smoothing `{prob['method']}`, scored out of sample above.
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
    prob = probabilistic_summary(bt, shipped)
    pd.DataFrame(prob["reliability"]).round(4).to_csv(common.OUTPUTS / "probability_reliability.csv", index=False)
    prob_json = {k: v for k, v in prob.items() if k not in ("reliability", "reliability_by_key")}
    payload = {"decision": info, "intervals": ivals, "probabilistic": prob_json,
               "metrics": metrics_df.to_dict(orient="records")}
    (common.OUTPUTS / "evaluation.json").write_text(json.dumps(study.round_floats(payload), indent=2), encoding="utf-8")
    write_report(metrics_df, bt, info, ivals, decision, prob, common.REPORTS / "evaluation.md")

    print("\nPooled MAE:")
    for target in config.TARGETS:
        row = {k: round(metric(metrics_df, target, "pooled", k, "mae"), 1) for k in METHOD_ORDER if k != "area_corrected"}
        print(f"  {target:15s} {row}")
    print(f"\nShipped model: {shipped} ({decision['selection_reason']})")
    print(f"Tier choice: {decision['tier_choice']}")
    for iv in ivals:
        print(f"  interval {iv['target']:15s} {iv['method']:17s} ratios {iv['q_low']:.3f}..{iv['q_high']:.3f}  "
              f"coverage in-sample {iv['coverage_pooled_in_sample']:.1%}, A->B {iv['coverage_fold_A_ratios_on_B']:.1%}")
    print(f"Probabilities: {prob['method_comparison']}")
    h = prob["headline"]
    print(f"  weighted_index {h['scored_on']}: Brier above {h['brier_above']:.4f} (base rates {h['brier_above_baseline']:.4f}), "
          f"below {h['brier_below']:.4f} ({h['brier_below_baseline']:.4f}), RPS {h['rps']:.4f} "
          f"(base rates {h['rps_baseline']:.4f}, hard tier {h['rps_hard_tier']:.4f})")
    print(f"  {h['statement']}")
    print(f"evaluate.py done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
