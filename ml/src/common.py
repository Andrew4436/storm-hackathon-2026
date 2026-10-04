"""Shared paths and small helpers for the ml/ pipeline.

Every script in ml/src does:
    import common          # puts ml/ on sys.path so `import config` works
and then uses common.REPO_ROOT, common.OUTPUTS, common.load_monthly(), ...

Paths are resolved from this file's location, so scripts run from any working directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]   # .../storm-hackathon-2026
ML_DIR = REPO_ROOT / "ml"
OUTPUTS = ML_DIR / "outputs"
REPORTS = REPO_ROOT / "reports"

if str(ML_DIR) not in sys.path:                   # make `import config` work from anywhere
    sys.path.insert(0, str(ML_DIR))

import config  # noqa: E402  (needs the sys.path line above)

# Short column prefixes used for the two targets in features.csv and elsewhere.
PREFIX = {"weighted_index": "wi", "incident_count": "ic"}

# The CBD has roughly 4x the activity of any other area, so we also report MAE without it.
CBD = "Central Business District"


def load_monthly() -> pd.DataFrame:
    """Read the processed neighbourhood x month table and add `weighted_index`.

    weighted_index = sum over the 8 type columns of (count x config.SEVERITY_WEIGHTS[column]).
    Rows are sorted by neighbourhood, then month, which every later step relies on.
    """
    df = pd.read_csv(REPO_ROOT / config.PROCESSED_CSV, dtype={config.MONTH_KEY: str})
    weights = pd.Series(config.SEVERITY_WEIGHTS)
    df["weighted_index"] = (df[config.TYPE_COLUMNS] * weights[config.TYPE_COLUMNS]).sum(axis=1).astype(int)
    df = df.sort_values([config.AREA_KEY, config.MONTH_KEY]).reset_index(drop=True)

    # Sanity checks on the invariants promised in data/README.md.
    assert (df[config.TYPE_COLUMNS].sum(axis=1) == df["incident_count"]).all(), "type columns must sum to incident_count"
    assert df.groupby(config.AREA_KEY)[config.MONTH_KEY].nunique().nunique() == 1, "every area needs the same months"
    return df


def add_months(month_str: str, k: int) -> str:
    """'2026-08' + 2 -> '2026-10'."""
    return str(pd.Period(month_str, freq="M") + k)


def month_name(month_str: str) -> str:
    """'2026-08' -> 'August 2026'."""
    return pd.Period(month_str, freq="M").strftime("%B %Y")
