"""Step 3: final fit on data through DATA_THROUGH -> forecast for FORECAST_MONTH + history export + meta.json.

1. Read the decision from ml/outputs/evaluation.json (run evaluate.py first).
2. Fit the shipped model (candidates.final_predict, the same code the backtest used) on all feature rows with
   TRAIN_START <= target_month <= DATA_THROUGH, for both targets.
3. Build each area's origin row at t = DATA_THROUGH and forecast T = FORECAST_MONTH.
4. 80% range: pooled backtest ratios (intervals.py) from the shipped model's weighted_index backtest predictions.
5. Tier: tiers.py with the config window / thresholds / reference, from the window ending DATA_THROUGH
   (the same rule that labels history and the backtest).
6. Drivers: 2-3 templated, factual sentences built from the features (no causes, only comparisons).

Writes ml/outputs/forecast_<FORECAST_MONTH>.csv / .json, ml/outputs/history.json, ml/outputs/meta.json, and fills
the "Forecast tier distribution" section of reports/evaluation.md.

Run from the repo root:  python ml/src/forecast.py
"""
from __future__ import annotations

import json
import re
import sys
import time

import numpy as np
import pandas as pd

import candidates
import common
import config
import intervals
import tiers
import train_poisson
from build_features import make_feature_table
from evaluate import FORECAST_SECTION_END, FORECAST_SECTION_START, load_features

OUTPUT_COLUMNS = ["neighbourhood", "month", "mode", "forecast_weighted_index", "forecast_incident_count",
                  "interval_low", "interval_high", "relative_activity_tier", "pct_vs_typical",
                  "baseline_weighted_index", "drivers", "data_through", "horizon_months", "model",
                  "typical_weighted_index"]
MONTH_EFFECT_MIN_PCT = 3.0     # only mention the GLM's seasonal adjustment when it is at least this large


# --------------------------------------------------------------------------- drivers
def compare(pct: float, what: str) -> str:
    """'11% above <what>' / '8% below <what>' / 'close to <what> (within 1%)'."""
    r = int(round(pct))
    if r == 0:
        return f"close to {what} (within 1%)"
    return f"{abs(r)}% {'above' if r > 0 else 'below'} {what}"


def drivers_for(row: pd.Series, tier_label: str | None, month_effect: float | None) -> list[str]:
    """Templated, factual sentences about the weighted index features of one area. Never causal."""
    if tier_label == tiers.INSUFFICIENT:
        return [f"Monthly counts here are too small to forecast meaningfully (about {row['area_mean_incidents']:.0f} "
                f"reported incidents per month over the last {config.TIER_WINDOW_MONTHS} months)."]
    m12 = row["wi_mean_12"]
    origin = pd.Period(config.DATA_THROUGH, freq="M")
    first3 = (origin - 2).strftime("%b")
    target = pd.Period(config.FORECAST_MONTH, freq="M")
    out = [
        f"Last 3 months ({first3}-{origin.strftime('%b %Y')}) were "
        + compare((row["wi_mean_3"] / m12 - 1) * 100, "this area's 12-month average"),
        f"{common.month_name(config.DATA_THROUGH)} was " + compare((row["wi_last_value"] / m12 - 1) * 100, "the 12-month average"),
    ]
    # With a seasonal tier reference the colour compares with last year's same month, so always say how that month went.
    if config.TIER_REFERENCE != "seasonal" and month_effect is not None and abs(month_effect) >= MONTH_EFFECT_MIN_PCT:
        out.append(f"The model's seasonal adjustment for {target.strftime('%B')} is {month_effect:+.0f}% "
                   "compared with an average month")
    else:
        out.append(f"{common.month_name(str(target - 12))} was "
                   + compare((row["wi_same_month_last_year"] / m12 - 1) * 100, "the latest 12-month average"))
    return out


# --------------------------------------------------------------------------- report section
def tier_distribution_md(counts: dict[str, int], n: int) -> str:
    order = tiers.TIERS + [tiers.INSUFFICIENT]
    lo, hi = config.TIER_THRESHOLDS_PCT
    lines = [f"Forecast for {config.FORECAST_MONTH} (thresholds {lo:+g}/{hi:+g}%, window {config.TIER_WINDOW_MONTHS} months, "
             f"reference `{config.TIER_REFERENCE}`), {n} areas:", "",
             "| tier | areas |", "|---|---|"]
    lines += [f"| {t} | {counts.get(t, 0)} |" for t in order]
    top, top_n = max(counts.items(), key=lambda kv: (kv[1], str(kv[0])))
    if top_n >= 20:
        lines += ["", f"**WARNING: {top_n} of {n} areas are `{top}`; the map would be nearly one colour.**"]
    return "\n".join(lines)


def update_report(section: str) -> None:
    path = common.REPORTS / "evaluation.md"
    if not path.exists():
        print("reports/evaluation.md not found; run evaluate.py to create it")
        return
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(FORECAST_SECTION_START) + ".*?" + re.escape(FORECAST_SECTION_END), re.S)
    new = pattern.sub(lambda _: f"{FORECAST_SECTION_START}\n{section}\n{FORECAST_SECTION_END}", text)
    path.write_text(new, encoding="utf-8")


# --------------------------------------------------------------------------- meta.json
def build_meta(evaluation: dict, model_name: str, ri: intervals.RatioInterval, counts: dict) -> dict:
    d = evaluation["decision"]
    m = pd.DataFrame(evaluation["metrics"])
    get = lambda method, col, fold="pooled": float(m.loc[(m.target == "weighted_index") & (m.fold == fold)  # noqa: E731
                                                       & (m.method == method), col].iloc[0])
    iv = next(x for x in evaluation["intervals"] if x["target"] == "weighted_index" and x["method"] == model_name)
    shipped_mae = get(model_name, "mae") if model_name != "area_corrected" else float("nan")
    m12, prev = get("mean_12", "mae"), get(config.REFERENCE_MODEL, "mae")
    lo, hi = config.TIER_THRESHOLDS_PCT
    noise = d["typical_area_noise"]
    notes = [
        "All values are reported incidents (or their severity-weighted index) per neighbourhood per month; "
        "nothing rates any place.",
        f"Model chosen by a rule fixed before the run (reports/model_study.md): {d['selection_reason']}.",
        f"Pooled = {d['n_pooled']} backtest rows (24 areas x 20 test months, {', '.join(f'{a}..{b}' for a, b in config.FOLDS.values())}), horizon {config.HORIZON_MONTHS}.",
        f"interval_coverage_pct is out-of-sample: ratios from fold A (2025) applied to fold B (2026); "
        f"in-sample pooled coverage is {iv['coverage_pooled_in_sample'] * 100:.0f}% by construction.",
        f"Range multipliers {ri.q_low:.3f}..{ri.q_high:.3f} x forecast (Q10..Q90 of actual/forecast over {ri.n_ratios} backtest points).",
        f"Tier: forecast vs {'the same calendar month in' if config.TIER_REFERENCE == 'seasonal' else 'the mean of'} the "
        f"last {config.TIER_WINDOW_MONTHS} complete months; below {lo:g}% / above +{hi:g}%; same rule for history and forecast.",
        f"tier_majority_baseline_pct = accuracy of always guessing the most common realised tier.",
        f"Noise floor: for the median area ({noise['median_area']}, ~{noise['median_area_incidents']:.0f} incidents/month) "
        f"Poisson noise alone is ~{noise['incident_count_pct']:.0f}% of a month's count.",
        f"2026-10 forecast tiers: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))) + ".",
        "Severity weights: Statistics Canada 85-004-X (2009) Table 1; CSI-inspired index, not the official CSI.",
    ]
    return {
        "app": "NeighbourCast",
        "model": model_name,
        "model_description": d["model_description"],
        "data_through": config.DATA_THROUGH,
        "forecast_month": config.FORECAST_MONTH,
        "horizon_months": config.HORIZON_MONTHS,
        "tier_window_months": config.TIER_WINDOW_MONTHS,
        "tier_thresholds_pct": [lo, hi],
        "tier_reference": config.TIER_REFERENCE,
        "interval_level": config.INTERVAL_LEVEL,
        "evaluation": {
            "folds": [{"name": f, "train_target_months": v["train_targets"], "test_target_months": v["test_targets"],
                       "n_train": v["n_train"], "n_test": v["n_test"]} for f, v in sorted(d["folds"].items())],
            "pooled_mae_weighted_index": {"mean_12": round(m12, 1), "previous_glm": round(prev, 1),
                                          "shipped": round(shipped_mae, 1)},
            "improvement_vs_mean_12_pct": round((m12 - shipped_mae) / m12 * 100, 1),
            "improvement_vs_previous_pct": round((prev - shipped_mae) / prev * 100, 1),
            "wape_pct": round(get(model_name, "wape_pct"), 1),
            "interval_coverage_pct": round(iv["coverage_fold_A_ratios_on_B"] * 100, 1),
            "tier_accuracy_pct": round(get(model_name, "tier_accuracy") * 100, 1),
            "tier_majority_baseline_pct": round(get(model_name, "tier_majority_baseline") * 100, 1),
            "tier_macro_f1": round(get(model_name, "tier_macro_f1"), 3),
        },
        "weights_source": config.WEIGHTS_SOURCE,
        "generated_from": config.PROCESSED_CSV,
        "notes": notes,
    }


# --------------------------------------------------------------------------- main
def none_if_nan(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else x


def main() -> None:
    t0 = time.time()
    eval_path = common.OUTPUTS / "evaluation.json"
    bt_path = common.OUTPUTS / "backtest_predictions.csv"
    if not eval_path.exists() or not bt_path.exists():
        sys.exit("Run python ml/src/evaluate.py first (needs evaluation.json and backtest_predictions.csv).")
    evaluation = json.loads(eval_path.read_text(encoding="utf-8"))
    decision = evaluation["decision"]
    model_name = decision["shipped_model"]

    monthly = common.load_monthly()
    features = load_features()
    train = features[(features["target_month"] >= config.TRAIN_START) & (features["target_month"] <= config.DATA_THROUGH)]

    # Origin rows at t = DATA_THROUGH (their target month is beyond the data, so they are not in features.csv).
    table = make_feature_table(monthly)
    origin = table[table["origin_month"] == config.DATA_THROUGH].reset_index(drop=True)
    assert len(origin) == monthly[config.AREA_KEY].nunique() == 24, "expected one origin row per area"
    assert (origin["target_month"] == config.FORECAST_MONTH).all(), "DATA_THROUGH + HORIZON_MONTHS must equal FORECAST_MONTH"

    preds, month_effect = {}, None
    for target, p in common.PREFIX.items():
        preds[target], glm = candidates.final_predict(model_name, train, origin, p, decision)
        if target == "weighted_index" and glm is not None:
            month_effect = train_poisson.month_effects(glm)[int(config.FORECAST_MONTH[5:7])]
    print(f"Fitted {model_name} on {len(train):,} rows per target (target months {train['target_month'].min()}.."
          f"{train['target_month'].max()})")

    # 80% range from the shipped model's weighted_index backtest ratios (both folds pooled).
    bt = pd.read_csv(bt_path, dtype={"origin_month": str, "target_month": str})
    bt = bt[(bt["target"] == "weighted_index") & bt[model_name].notna()]
    ri = intervals.fit_ratios(bt["actual"], bt[model_name])
    low, high = ri.apply(preds["weighted_index"])
    print(f"Interval ratios Q-low {ri.q_low:.3f}, Q-high {ri.q_high:.3f} from {ri.n_ratios} backtest points")

    # Typical level for FORECAST_MONTH from the window ending DATA_THROUGH (same rule as history and backtest).
    typ = monthly[[config.AREA_KEY, config.MONTH_KEY]].copy()
    typ["typical_wi"] = tiers.typical_level(monthly, "weighted_index", config.HORIZON_MONTHS)
    typ["area_mean_incidents"] = tiers.trailing_mean(monthly, "incident_count")
    typ = typ[typ[config.MONTH_KEY] == config.DATA_THROUGH].drop(columns=config.MONTH_KEY)
    origin = origin.merge(typ, on=config.AREA_KEY, how="left")

    records = []
    for i, row in origin.iterrows():
        f_wi = float(preds["weighted_index"][i])
        tier_label, pct = tiers.tier(f_wi, row["typical_wi"], row["area_mean_incidents"])
        records.append({
            "neighbourhood": row[config.AREA_KEY],
            "month": config.FORECAST_MONTH,
            "mode": "forecast",
            "forecast_weighted_index": int(round(f_wi)),
            "forecast_incident_count": int(round(float(preds["incident_count"][i]))),
            "interval_low": int(round(float(low[i]))),
            "interval_high": int(round(float(high[i]))),
            "relative_activity_tier": tier_label,
            "pct_vs_typical": tiers.round_pct(pct),
            "baseline_weighted_index": int(round(row["wi_mean_12"])),
            "drivers": drivers_for(row, tier_label, month_effect),
            "data_through": config.DATA_THROUGH,
            "horizon_months": config.HORIZON_MONTHS,
            "model": model_name,
            # The level pct_vs_typical is measured against (additive field; baseline_weighted_index stays the 12-month mean).
            "typical_weighted_index": None if pd.isna(row["typical_wi"]) else int(round(row["typical_wi"])),
        })
    records.sort(key=lambda r: r["neighbourhood"])

    # ---- forecast files
    stem = f"forecast_{config.FORECAST_MONTH}"
    (common.OUTPUTS / f"{stem}.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    csv = pd.DataFrame(records)[OUTPUT_COLUMNS]
    csv["drivers"] = csv["drivers"].map(" | ".join)
    csv.to_csv(common.OUTPUTS / f"{stem}.csv", index=False)

    # ---- history.json (from history.csv written by build_features.py, same tiers.py rule)
    hist = pd.read_csv(common.OUTPUTS / "history.csv", dtype={"month_str": str})
    hist_records = [{
        "neighbourhood": r.neighbourhood,
        "month": r.month_str,
        "weighted_index": int(r.weighted_index),
        "incident_count": int(r.incident_count),
        "relative_activity_tier": none_if_nan(r.relative_activity_tier),
        "pct_vs_typical": none_if_nan(r.pct_vs_typical),
        "is_partial": int(r.is_partial),
    } for r in hist.itertuples(index=False)]
    assert len(hist_records) == 6840, f"history.json should have 6,840 rows, got {len(hist_records)}"
    (common.OUTPUTS / "history.json").write_text(json.dumps(hist_records, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---- consistency check: history.csv must have been built with the same tier settings
    check = tiers.history_tiers(monthly)["tier"].fillna("(none)").to_numpy()
    assert (check == hist["relative_activity_tier"].fillna("(none)").to_numpy()).all(), \
        "history.csv tiers differ from config: re-run build_features.py"

    # ---- tier distribution (console + report) and meta.json
    counts = {}
    for r in records:
        counts[r["relative_activity_tier"]] = counts.get(r["relative_activity_tier"], 0) + 1
    section = tier_distribution_md(counts, len(records))
    update_report(section)
    meta = build_meta(evaluation, model_name, ri, counts)
    (common.OUTPUTS / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(csv[["neighbourhood", "forecast_weighted_index", "interval_low", "interval_high", "forecast_incident_count",
               "relative_activity_tier", "pct_vs_typical", "typical_weighted_index"]].to_string(index=False))
    print("\n" + section)
    print(f"forecast.py done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
