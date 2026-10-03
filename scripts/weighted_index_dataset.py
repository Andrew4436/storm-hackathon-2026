"""Clean VPD raw incident data and build a monthly weighted-index dataset.

Input columns expected from the VPD CSV:
TYPE,YEAR,MONTH,DAY,HOUR,MINUTE,HUNDRED_BLOCK,NEIGHBOURHOOD,X,Y

This script intentionally excludes homicide and vehicle-collision categories,
as agreed by the team. It does not deduplicate rows: the supplied data has no
unique incident ID, and identical-looking rows may still be distinct events.

Example:
    python build_weighted_index_dataset.py \
      --input data/raw/vpd_incidents.csv \
      --output-dir data/processed
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


# Prototype, CSI-inspired weights. These are not official CSI weights because
# VPD's TYPE labels are broader than official UCR offence codes.
SEVERITY_WEIGHTS = {
    "Other Theft": 29,
    "Theft from Vehicle": 29,
    "Mischief": 24,
    "Offence Against a Person": 60,
    "Break and Enter Residential/Other": 147,
    "Break and Enter Commercial": 147,
    "Theft of Vehicle": 66,
    "Theft of Bicycle": 29,
}

REQUIRED_COLUMNS = {"TYPE", "YEAR", "MONTH", "NEIGHBOURHOOD"}


def validate_and_clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Validate raw records and return weighted records plus unmapped types."""
    raw = raw.copy()
    raw.columns = [str(column).strip().upper() for column in raw.columns]
    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    original_rows = len(raw)

    # Normalize strings only; do not alter geography or infer missing locations.
    raw["TYPE"] = raw["TYPE"].astype("string").str.strip()
    raw["NEIGHBOURHOOD"] = raw["NEIGHBOURHOOD"].astype("string").str.strip()
    raw["YEAR"] = pd.to_numeric(raw["YEAR"], errors="coerce")
    raw["MONTH"] = pd.to_numeric(raw["MONTH"], errors="coerce")

    valid = raw[
        raw["TYPE"].notna()
        & raw["NEIGHBOURHOOD"].notna()
        & raw["YEAR"].between(2003, 2100)
        & raw["MONTH"].between(1, 12)
    ].copy()
    valid["YEAR"] = valid["YEAR"].astype(int)
    valid["MONTH"] = valid["MONTH"].astype(int)

    unmapped_types = (
        valid.loc[~valid["TYPE"].isin(SEVERITY_WEIGHTS), ["TYPE"]]
        .value_counts()
        .rename("row_count")
        .reset_index()
        .sort_values("row_count", ascending=False)
    )

    weighted = valid.loc[valid["TYPE"].isin(SEVERITY_WEIGHTS)].copy()
    weighted["severity_weight"] = weighted["TYPE"].map(SEVERITY_WEIGHTS).astype(int)
    weighted["weighted_incident_value"] = weighted["severity_weight"]
    weighted["date"] = pd.to_datetime(
        {"year": weighted["YEAR"], "month": weighted["MONTH"], "day": 1}
    )

    report = {
        "input_rows": int(original_rows),
        "rows_after_required_field_validation": int(len(valid)),
        "rows_excluded_missing_or_invalid_required_fields": int(original_rows - len(valid)),
        "rows_included_in_weighted_index": int(len(weighted)),
        "rows_excluded_unmapped_or_intentionally_out_of_scope_types": int(
            len(valid) - len(weighted)
        ),
        "weights": SEVERITY_WEIGHTS,
        "note": (
            "weighted_index is an experimental CSI-inspired prototype indicator, "
            "not Statistics Canada's official Crime Severity Index."
        ),
    }
    return weighted, unmapped_types, report


def build_monthly_index(weighted: pd.DataFrame) -> pd.DataFrame:
    """Aggregate event rows into one neighbourhood-month modelling record."""
    monthly = (
        weighted.groupby(["NEIGHBOURHOOD", "YEAR", "MONTH", "date"], as_index=False)
        .agg(
            raw_incident_count=("TYPE", "size"),
            weighted_index=("weighted_incident_value", "sum"),
        )
        .rename(
            columns={
                "NEIGHBOURHOOD": "neighbourhood",
                "YEAR": "year",
                "MONTH": "month",
            }
        )
        .sort_values(["neighbourhood", "date"])
        .reset_index(drop=True)
    )
    return monthly


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a monthly CSI-inspired weighted-index dataset from VPD raw data."
    )
    parser.add_argument("--input", required=True, help="Path to the raw VPD CSV")
    parser.add_argument(
        "--output-dir", default="data/processed", help="Directory for generated CSV/JSON files"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.input, low_memory=False)
    weighted, unmapped_types, report = validate_and_clean(raw)
    monthly = build_monthly_index(weighted)

    # Event-level export is useful for auditing weights; it excludes unnecessary
    # location/time fields so the downstream project uses area-level data only.
    event_level = weighted[
        ["TYPE", "NEIGHBOURHOOD", "YEAR", "MONTH", "date", "severity_weight"]
    ].rename(
        columns={
            "TYPE": "crime_type",
            "NEIGHBOURHOOD": "neighbourhood",
            "YEAR": "year",
            "MONTH": "month",
        }
    )

    event_path = output_dir / "weighted_incidents_clean.csv"
    monthly_path = output_dir / "neighbourhood_monthly_weighted_index.csv"
    unmapped_path = output_dir / "unmapped_or_excluded_types.csv"
    report_path = output_dir / "weighted_index_data_quality_report.json"

    event_level.to_csv(event_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    unmapped_types.to_csv(unmapped_path, index=False)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("Created:")
    print(f"  {event_path}")
    print(f"  {monthly_path}")
    print(f"  {unmapped_path}")
    print(f"  {report_path}")
    print(f"\nMonthly rows: {len(monthly)}")
    print(f"Neighbourhoods: {monthly['neighbourhood'].nunique()}")
    print(f"Date range: {monthly['date'].min().date()} to {monthly['date'].max().date()}")


if __name__ == "__main__":
    main()
