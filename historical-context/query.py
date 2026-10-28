#!/usr/bin/env python3
"""Query a historical CGWB groundwater or CPCB surface-water profile."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

# Running this file directly puts historical-context/ on sys.path, including
# when the caller's current directory is the repository root or elsewhere.
from src.historical_context import SOURCE_DATASETS, get_historical_profile

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSVS = {
    "groundwater": SCRIPT_DIR / "datasets/raw/gwq_chemical_parameter_manual_cgwb_up_1961_2025.csv",
    "surface_water": SCRIPT_DIR / "datasets/raw/swq_physical_parameter_manual_cpcb_up_2021_2025.csv",
}


def _iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("date must use YYYY-MM-DD spelling")
        return parsed.isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a valid YYYY-MM-DD date") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show descriptive historical water-quality context for a location."
    )
    parser.add_argument("--source", required=True, choices=tuple(SOURCE_DATASETS))
    parser.add_argument("--location", required=True, help="exact station or locality text to match")
    parser.add_argument("--as-of", type=_iso_date, metavar="YYYY-MM-DD",
                        help="reference date for record age (defaults to current UTC date)")
    parser.add_argument("--csv", type=Path, help="override the source's default CSV path")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def _display(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def format_readable(result: dict[str, Any], dataset_path: Path) -> str:
    profile = result["profile"]
    level = profile["match_level"]
    if level == "ambiguous":
        match_status = "AMBIGUOUS: more than one station identity has this exact name"
    elif level == "unmatched":
        match_status = "NO MATCH"
    else:
        match_status = "MATCHED"

    lines = [
        f"Source agency: {profile['dataset_agency']}",
        f"Dataset: {dataset_path}",
        f"Requested location: {profile['requested_location']}",
        f"Match result: {match_status}",
        f"Match level: {_display(level)}",
        f"Matched field: {_display(profile['matched_column'])}",
        f"Observations: {profile['sample_count']}",
        f"Reference date (UTC): {_display(profile['reference_date'])}",
        f"Earliest valid sample date: {_display(profile['earliest_sample_date'])}",
        f"Latest valid sample date: {_display(profile['latest_sample_date'])}",
        f"Age of latest sample (days): {_display(profile['record_age_days'])}",
        f"Missing sample dates: {_display(profile['date_missing_count'])}",
    ]
    if "stale_record" in profile["data_quality_flags"]:
        lines.append("WARNING: the latest available sample is more than 365 days old.")
    lines.extend(["", "Water-quality parameters:"])
    if not profile["parameters"]:
        lines.append("  (none available for this query)")
    for name, summary in profile["parameters"].items():
        unit = summary["unit"] or "not specified by source schema"
        lines.extend([
            f"  {name} [{unit}]",
            f"    Valid measurements: {summary['measurement_count']}",
            f"    Missing measurements: {summary['missing_count']}",
            f"    Latest valid measurement date: {_display(summary['latest_measurement_date'])}",
            f"    Measurement age (days): {_display(summary['measurement_age_days'])}",
            f"    Stale measurement: {_display(summary['stale_measurement'])}",
        ])
        if summary["measurement_status"] == "no_valid_measurements":
            lines.append("    Measurement status: no valid measurement; date and staleness cannot be assessed.")
        elif summary["measurement_status"] == "measurement_date_unavailable":
            lines.append("    Measurement status: value(s) exist, but no valid measurement date is available.")
        elif summary["measurement_status"] == "partial_measurement_dates":
            lines.append("    Measurement status: some valid values have no dates; age and staleness may be incomplete.")
        for measurement_flag in summary["measurement_quality_flags"]:
            if measurement_flag == "stale_measurement":
                lines.append("    WARNING: this parameter's latest valid measurement is more than 365 days old.")
            else:
                lines.append(f"    Measurement flag: {measurement_flag}")
        if summary["observed_categories"] is not None:
            categories = summary["observed_categories"]
            lines.append("    Observed categories: " + (", ".join(f"{key}: {count}" for key, count in categories.items()) or "N/A"))
        else:
            lines.extend([
                f"    Mean: {_display(summary['mean'])}",
                f"    Median: {_display(summary['median'])}",
                f"    Minimum: {_display(summary['min'])}",
                f"    Maximum: {_display(summary['max'])}",
                f"    Standard deviation: {_display(summary['std'])}",
            ])

    flags = profile["data_quality_flags"]
    lines.extend(["", "Data-quality flags:"])
    lines.extend(f"  - {flag}" for flag in flags) if flags else lines.append("  (none)")
    zero_diagnostic = profile["zero_value_diagnostics"]
    lines.extend(["", "Trace-metal zero-value diagnostic:"])
    zero_values = zero_diagnostic["trace_metal_parameters_with_zero_values"]
    lines.extend(
        f"  - {item['parameter']}: {item['zero_count']} recorded numeric zero value(s)"
        for item in zero_values
    )
    if not zero_values:
        lines.append("  No trace-metal numeric zeros observed in this matched profile.")
    lines.append(f"  Caution: {zero_diagnostic['caution']}")
    if level == "ambiguous":
        lines.append(f"Candidate observations needing disambiguation: {profile['candidate_sample_count']}")
        for candidate in profile["ambiguous_candidates"]:
            location = ", ".join(f"{k}={v}" for k, v in candidate["location"].items()) or "location metadata unavailable"
            lines.append(f"  - {candidate['station']}: {location} ({candidate['observation_count']} observations)")
    lines.extend([
        "",
        "Limitations:",
        "  - These are historical observations, not current water-quality readings.",
        "  - Exact text matching does not prove geographic proximity.",
        "  - This summary does not determine whether water is safe or unsafe.",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dataset_path = (args.csv if args.csv is not None else DEFAULT_CSVS[args.source]).expanduser().resolve()
    try:
        profile = get_historical_profile(
            dataset_path,
            args.source,
            args.location,
            as_of=args.as_of,
        )
    except (FileNotFoundError, ValueError, pd.errors.ParserError, OSError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    result = {"dataset_path": str(dataset_path), "profile": profile}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    else:
        print(format_readable(result, dataset_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
