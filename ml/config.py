"""Single source of truth for the ml-forecast branch. Change values here, never in scripts.

See docs/ML_TEAM_CONTRACT.md for the reasoning behind every value.
"""

# --- data -----------------------------------------------------------------
PROCESSED_CSV = "data/processed/neighbourhood_monthly.csv"   # relative to repo root
MONTH_KEY = "month_str"                                       # YYYY-MM
AREA_KEY = "neighbourhood"

# --- severity weights (Crime Severity Index approach) ----------------------
# TODO before demo: cite the Statistics Canada CSI weight table used and the
# VPD TYPE -> CSI offence mapping for each line. Working values from the
# ml-forecast draft of 2026-10-03.
SEVERITY_WEIGHTS = {
    "other_theft": 29,
    "theft_from_vehicle": 29,
    "mischief": 24,
    "offence_against_a_person": 60,
    "break_and_enter_residential_other": 147,
    "break_and_enter_commercial": 147,
    "theft_of_vehicle": 66,
    "theft_of_bicycle": 29,
}
TYPE_COLUMNS = list(SEVERITY_WEIGHTS)            # the 8 per-type count columns in the processed csv
TARGETS = ["weighted_index", "incident_count"]   # primary first

# --- horizon ---------------------------------------------------------------
DATA_THROUGH = "2026-08"       # last complete month; 2026-09 is partial (is_partial == 1)
HORIZON_MONTHS = 2
FORECAST_MONTH = "2026-010"

# --- features --------------------------------------------------------------
LAG_WINDOWS = [3, 6, 12]       # mean_3, mean_6, mean_12 over t-(k-1)..t
LOG1P_FEATURES_FOR_GLM = True  # count-like features enter the Poisson GLM as log1p(x)

# --- evaluation ------------------------------------------------------------
TRAIN_START = "2010-01"        # first target month used for training
FOLDS = {                      # split by TARGET month; train on everything earlier
    "A": ("2025-01", "2025-12"),
    "B": ("2026-01", "2026-08"),
}
BASELINES = ["mean_3", "mean_12", "same_month_last_year"]
DECISION_METRIC = "mae_pooled_weighted_index"   # lower wins; fixed before the final run

# --- random forest ---------------------------------------------------------
RF_PARAMS = {"n_estimators": 500, "min_samples_leaf": 5, "random_state": 0, "n_jobs": -1}

# --- poisson glm -----------------------------------------------------------
GLM_PARAMS = {"alpha": 1e-4, "max_iter": 3000}

# --- uncertainty -----------------------------------------------------------
INTERVAL_LEVEL = 0.80          # from backtest ratios actual/forecast pooled across areas, Q10..Q90

# --- tiers -----------------------------------------------------------------
TIER_WINDOW_MONTHS = 12       # each area's own trailing complete months define "typical"
TIER_THRESHOLDS_PCT = (-5.0, 5.0)   # below_typical < -5%, typical within, above_typical > +5%; tune at 7 PM checkpoint
TIER_MIN_MEAN = 10             # areas averaging fewer than this per month get "insufficient_data" (Musqueam)
