"""Single source of truth for the ml-forecast branch. Change values here, never in scripts.

See docs/ML_TEAM_CONTRACT.md for the reasoning behind every value.
"""

# --- data -----------------------------------------------------------------
PROCESSED_CSV = "data/processed/neighbourhood_monthly.csv"   # relative to repo root
MONTH_KEY = "month_str"                                       # YYYY-MM
AREA_KEY = "neighbourhood"

# --- severity weights (CSI-inspired, official published weights) ----------
# Source: Statistics Canada, Wallace, M. et al. (2009) "Measuring Crime in Canada: Introducing the Crime Severity
# Index and Improvements to the Uniform Crime Reporting Survey", catalogue no. 85-004-X, Table 1
# "Examples of weights for the Crime Severity Index" (weights from court sentencing data 2002/03..2006/07).
#   https://www150.statcan.gc.ca/n1/pub/85-004-x/2009001/t001-eng.htm
#   https://www150.statcan.gc.ca/n1/pub/85-004-x/85-004-x2009001-eng.pdf
# StatCan has re-weighted the CSI since 2009; we did not find a public table of the current per-offence
# weights, so these are the 2009 published values. The index is CSI-INSPIRED, not the official CSI (the official
# CSI uses ~all Criminal Code offences and divides by population; we use 8 VPD types per neighbourhood-month).
#
# Changed on 2026-10-04: the working values of 2026-10-03 (29/29/24/60/147/147/66/29) were these published
# weights x ~0.786, rounded; the relative weights are unchanged to within 2%, so only the scale of the index
# moved (about +27%). Old value in brackets on each line.
SEVERITY_WEIGHTS = {
    "other_theft": 37,                          # CSI "Theft under $5,000" = 37            [was 29]
    "theft_from_vehicle": 37,                   # CSI "Theft under $5,000" = 37            [was 29]
    "mischief": 30,                             # CSI "Mischief" = 30                      [was 24]
    "offence_against_a_person": 77,             # CSI "Assault - level 2" = 77 (weakest mapping: the VPD type
                                                #  mixes assault levels 1-3 (23/77/405), robbery (583) and sexual
                                                #  offences; level 2 is close to the CSI average weight, 69) [was 60]
    "break_and_enter_residential_other": 187,   # CSI "Breaking and entering" = 187        [was 147]
    "break_and_enter_commercial": 187,          # CSI "Breaking and entering" = 187        [was 147]
    "theft_of_vehicle": 84,                     # CSI "Theft of a motor vehicle" = 84      [was 66]
    "theft_of_bicycle": 37,                     # CSI "Theft under $5,000" = 37            [was 29]
}
WEIGHTS_SOURCE = "https://www150.statcan.gc.ca/n1/pub/85-004-x/2009001/t001-eng.htm"
WEIGHTS_SOURCE_TABLE = ("Statistics Canada 85-004-X (2009), Table 1 'Examples of weights for the Crime Severity "
                        "Index'")
TYPE_COLUMNS = list(SEVERITY_WEIGHTS)            # the 8 per-type count columns in the processed csv
TARGETS = ["weighted_index", "incident_count"]   # primary first

# --- horizon ---------------------------------------------------------------
DATA_THROUGH = "2026-08"       # last complete month; 2026-09 is partial (is_partial == 1)
HORIZON_MONTHS = 2
FORECAST_MONTH = "2026-10"

# --- features --------------------------------------------------------------
LAG_WINDOWS = [3, 6, 12]       # mean_3, mean_6, mean_12 over t-(k-1)..t
LONG_WINDOWS = [24, 36]        # mean_24, mean_36 (extended GLM and boosting only)
LOG1P_FEATURES_FOR_GLM = True  # count-like features enter the Poisson GLM as log1p(x)
MOMENTUM_TYPES = ["other_theft", "theft_from_vehicle", "mischief"]   # 3 largest types (2024-2026 counts)

# --- evaluation ------------------------------------------------------------
TRAIN_START = "2010-01"        # first target month used for training
FOLDS = {                      # split by TARGET month; train on everything earlier
    "A": ("2025-01", "2025-12"),
    "B": ("2026-01", "2026-08"),
}
BASELINES = ["mean_3", "mean_12", "same_month_last_year"]
DECISION_METRIC = "mae_pooled_weighted_index"   # lower wins; fixed before the final run

# Model selection rule, pre-registered 2026-10-04 before the model study was run (see reports/model_study.md):
# ship the candidate with the lowest pooled weighted_index MAE among those that beat the reference GLM (C0)
# on fold B by at least SELECTION_MIN_FOLD_B_GAIN_PCT and on pooled MAE; a simpler qualifier within
# SELECTION_TIE_PCT of the best pooled MAE wins the tie. If nothing qualifies, C0 stays.
REFERENCE_MODEL = "poisson_glm"
SELECTION_MIN_FOLD_B_GAIN_PCT = 1.0
SELECTION_TIE_PCT = 1.0

# --- random forest ---------------------------------------------------------
RF_PARAMS = {"n_estimators": 500, "min_samples_leaf": 5, "random_state": 0, "n_jobs": -1}

# --- poisson glm -----------------------------------------------------------
GLM_PARAMS = {"alpha": 1e-4, "max_iter": 3000}

# --- gradient boosting (candidate C3) ---------------------------------------
HGB_PARAMS = {"loss": "poisson", "learning_rate": 0.05, "max_leaf_nodes": 15, "random_state": 0}
HGB_MAX_ITER = 400
HGB_ITER_STEP = 10
HGB_VALIDATION_MONTHS = 12     # early stopping on the last 12 target months of each training set (time-ordered)

# --- uncertainty -----------------------------------------------------------
INTERVAL_LEVEL = 0.80          # from backtest ratios actual/forecast pooled across areas, Q10..Q90

# --- tiers -----------------------------------------------------------------
# Chosen by the tier study on 2026-10-04 (reports/model_study.md, "Tier decision"): no grid cell met both
# pre-registered constraints, so the fallback (readable 2026-10 map, best skill) picked 12 / +-10% / seasonal,
# i.e. "more than 10% above or below the same month last year". Applied identically to history, backtest and forecast.
TIER_WINDOW_MONTHS = 12        # each area's own trailing complete months define "typical"
TIER_THRESHOLDS_PCT = (-10.0, 10.0) # below_typical < low, typical within, above_typical > high
TIER_REFERENCE = "seasonal"         # "trailing_mean" (mean of the window) or "seasonal" (same calendar month in the window)
TIER_MIN_MEAN = 10             # areas averaging fewer than this per month get "insufficient_data" (Musqueam)
