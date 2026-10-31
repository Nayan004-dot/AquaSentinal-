
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

SOURCE_DATASETS = {"groundwater": "CGWB", "surface_water": "CPCB"}
DATE_COLUMNS = ("Data Acquisition Time", "Sample Date", "Date", "datetime")
MATCH_COLUMNS = ("Station", "Village", "Block", "Tehsil", "District", "River")
STALE_AFTER_DAYS = 365

# These are the measurement fields in the supplied source schemas, explicitly
# listed so appended identifiers or other metadata can never become parameters.
MEASUREMENT_COLUMNS = {
    "groundwater": (
        "Potential of Hydrogen (pH)", "Electric Conductivity (μS/cm)",
        "Total Dissolved Solids (mg/L)", "Carbonate (mg/L)", "Bicarbonate (mg/L)",
        "Total Alkalinity (mg/L as CaCO3)", "Chloride (mg/L)", "Nitrate N (mgN/L)",
        "Sulphate (mg/L)", "Phosphate(mg/L)", "Silica(mg/L)", "Fluoride (mg/L)",
        "Total Hardness (mgCaCO3/L)", "Calcium (mg/L)", "Magnesium (mg/L)",
        "Sodium (mg/L)", "Potassium (mg/L)", "Iron(mg/L)", "Arsenic (mg/L)",
        "Uranium(mg/L)", "Manganese (mg/L)", "Copper (mg/L)", "Lead (mg/L)",
        "Zinc (mg/L)", "Nickel (mg/L)", "Cadmium (mg/L)", "Chromium (mg/L)",
    ),
    "surface_water": (
        "Electric Conductivity (μS/cm)", "Colour", "Odour", "Turbidity (NTU)",
        "Temperature (ºC)", "Total Solids (mg/L)",
    ),
}
STATION_IDENTITY_COLUMNS = (
    "State", "District", "Tehsil", "Block", "Village", "River", "Latitude", "Longitude",
)
TRACE_METAL_PARAMETERS = (
    "Iron(mg/L)", "Arsenic (mg/L)", "Uranium(mg/L)", "Manganese (mg/L)",
    "Copper (mg/L)", "Lead (mg/L)", "Zinc (mg/L)", "Nickel (mg/L)",
    "Cadmium (mg/L)", "Chromium (mg/L)",
)
TRACE_METAL_PARAMETER_NAMES = {name.casefold() for name in TRACE_METAL_PARAMETERS}
ZERO_VALUE_CAUTION = (
    "A recorded numeric zero is retained as supplied. Its analytical meaning has not been verified; "
    "it does not establish that a contaminant is absent or below a detection limit."
)


def load_csv(csv_path: str | Path) -> pd.DataFrame:
    """Load a CSV while retaining source column names and values."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    try:
        return pd.read_csv(path, low_memory=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"Dataset has no CSV header: {path}") from exc


def _column(df: pd.DataFrame, name: str) -> str | None:
    wanted = name.strip().casefold()
    return next((str(c) for c in df.columns if str(c).strip().casefold() == wanted), None)


def _parse_one_date(value: Any) -> pd.Timestamp | pd.NaT:
    if pd.isna(value) or not str(value).strip():
        return pd.NaT
    raw = str(value).strip()
    parsed = None
    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            parsed = pd.Timestamp(datetime.strptime(raw, fmt))
            break
        except ValueError:
            continue
    if parsed is None:
        # ISO forms are unambiguous and include optional time-zone offsets.
        if not (len(raw) >= 10 and raw[0:4].isdigit() and raw[4] == "-"):
            return pd.NaT
        try:
            parsed = pd.Timestamp(raw)
        except (TypeError, ValueError, OverflowError):
            return pd.NaT
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _parse_dates(values: pd.Series) -> pd.Series:
    """Parse supported day-first source dates and ISO dates, normalized to UTC."""
    return pd.Series(pd.to_datetime([_parse_one_date(v) for v in values], utc=True), index=values.index)


def _reference_date(as_of: str | pd.Timestamp | None) -> pd.Timestamp:
    if as_of is None:
        return pd.Timestamp.now(tz="UTC").normalize()
    try:
        if isinstance(as_of, str):
            # Restrict strings to ISO-8601 so values such as 01-02-2024
            # cannot be silently interpreted using month/day conventions.
            reference = pd.Timestamp(datetime.fromisoformat(as_of.strip().replace("Z", "+00:00")))
        else:
            reference = pd.Timestamp(as_of)
        if pd.isna(reference):
            raise ValueError("as_of must be a valid date or timestamp")
        if reference.tzinfo is None:
            reference = reference.tz_localize("UTC")
        else:
            reference = reference.tz_convert("UTC")
        return reference.normalize()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid as_of reference date: {as_of!r}") from exc


def _clean_text(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return None if not text or text == "-" else text


def _station_candidates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Describe distinct station identities for an exact station-name query."""
    station_col = _column(df, "Station")
    if station_col is None:
        return []
    identity_cols = [(name, _column(df, name)) for name in STATION_IDENTITY_COLUMNS]
    normalized_rows = [
        tuple(_clean_text(row[col]) if col else None for _, col in identity_cols)
        for _, row in df.iterrows()
    ]
    # Missing metadata should not turn repeated observations into separate
    # candidate stations. Ambiguity requires conflicting observed identity data.
    has_conflicts = any(
        len({signature[index] for signature in normalized_rows if signature[index] is not None}) > 1
        for index in range(len(identity_cols))
    )
    if not has_conflicts:
        representative = tuple(
            next((signature[index] for signature in normalized_rows if signature[index] is not None), None)
            for index in range(len(identity_cols))
        )
        return [{
            "station": _clean_text(df.iloc[0][station_col]),
            "observation_count": len(df),
            "location": {name: value for (name, _), value in zip(identity_cols, representative) if value is not None},
        }]
    candidates: dict[tuple[Any, ...], dict[str, Any]] = {}
    for (_, row), identity in zip(df.iterrows(), normalized_rows):
        # Without any differentiating context, repeated rows are observations of
        # the same named station, not evidence of multiple stations.
        key = identity
        entry = candidates.setdefault(key, {"station": _clean_text(row[station_col]), "observation_count": 0, "location": {}})
        entry["observation_count"] += 1
        if not entry["location"]:
            entry["location"] = {name: value for (name, _), value in zip(identity_cols, identity) if value is not None}
    return list(candidates.values())


def _unit_from_name(parameter: str) -> str | None:
    if parameter.strip().casefold() == "potential of hydrogen (ph)":
        return None
    if "(" not in parameter or ")" not in parameter:
        return None
    return parameter.rsplit("(", 1)[1].split(")", 1)[0].strip() or None


def _finite_number(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _empty_profile(source_type: str, requested: str, *, match_level: str = "unmatched",
                   matched_column: str | None = None, flags: list[str] | None = None,
                   candidates: list[dict[str, Any]] | None = None,
                   candidate_sample_count: int = 0,
                   measurement_columns_present: list[str] | None = None,
                   measurement_columns_missing: list[str] | None = None,
                   date_column: str | None = None,
                   reference_date: str | None = None) -> dict[str, Any]:
    return {
        "source_type": source_type, "dataset_agency": SOURCE_DATASETS[source_type],
        "requested_location": requested, "match_level": match_level,
        "matched_column": matched_column, "sample_count": 0,
        "candidate_sample_count": candidate_sample_count,
        "earliest_sample_date": None, "latest_sample_date": None,
        "record_age_days": None, "date_missing_count": None,
        "date_column": date_column, "reference_date": reference_date,
        "parameters": {}, "ambiguous_candidates": candidates or [],
        "zero_value_diagnostics": {
            "trace_metal_parameters_with_zero_values": [],
            "caution": ZERO_VALUE_CAUTION,
        },
        "measurement_columns_present": measurement_columns_present or [],
        "measurement_columns_missing": measurement_columns_missing or [],
        "data_quality_flags": flags or [], "geographic_proximity_established": False,
        "historical_data_only": True,
    }


def get_historical_profile(
    csv_path: str | Path,
    source_type: str,
    location: str,
    *,
    as_of: str | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable profile from a CGWB or CPCB historical CSV.

    Exact case-insensitive matching order is station, village, block, tehsil,
    district, river. An exact station-name match spanning distinct location
    identities is returned as ambiguous with no aggregated measurements.
    Matching text does not establish geographic proximity.
    """
    if not isinstance(source_type, str) or source_type.strip().casefold() not in SOURCE_DATASETS:
        raise ValueError("source_type must be 'groundwater' or 'surface_water'")
    source_type = source_type.strip().casefold()
    if not isinstance(location, str) or not location.strip():
        raise ValueError("location must not be empty")
    requested = location.strip()
    reference = _reference_date(as_of)
    reference_date = reference.date().isoformat()
    df = load_csv(csv_path)

    flags: list[str] = []
    location_cols = {level: _column(df, level) for level in MATCH_COLUMNS}
    if not any(location_cols.values()):
        flags.append("missing_location_columns")
    date_col = next((col for name in DATE_COLUMNS if (col := _column(df, name))), None)
    if date_col is None:
        flags.append("missing_date_column")
        dates = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    else:
        dates = _parse_dates(df[date_col])
    present_measurements = [
        col for expected in MEASUREMENT_COLUMNS[source_type]
        if (col := _column(df, expected)) is not None
    ]
    missing_measurements = [name for name in MEASUREMENT_COLUMNS[source_type] if _column(df, name) is None]
    if missing_measurements:
        flags.append("missing_measurement_columns")

    if df.empty:
        flags.append("empty_dataset")
        return _empty_profile(source_type, requested, flags=flags,
                              measurement_columns_present=present_measurements,
                              measurement_columns_missing=missing_measurements, date_column=date_col,
                              reference_date=reference_date)

    matched_column = None
    matched_rows = df.iloc[0:0]
    for level in MATCH_COLUMNS:
        col = location_cols[level]
        if col is None:
            continue
        values = df[col].astype("string").str.strip()
        mask = values.str.casefold().eq(requested.casefold()).fillna(False)
        if mask.any():
            matched_column, matched_rows = col, df.loc[mask]
            break

    if matched_column is None:
        flags.append("unmatched_location")
        return _empty_profile(source_type, requested, flags=flags,
                              measurement_columns_present=present_measurements,
                              measurement_columns_missing=missing_measurements, date_column=date_col,
                              reference_date=reference_date)

    if matched_column.casefold() == "station":
        identities = _station_candidates(matched_rows)
        if len(identities) > 1:
            flags.append("ambiguous_station_name")
            return _empty_profile(
                source_type, requested, match_level="ambiguous", matched_column=matched_column,
                flags=flags, candidates=identities, candidate_sample_count=len(matched_rows),
                measurement_columns_present=present_measurements,
                measurement_columns_missing=missing_measurements, date_column=date_col,
                reference_date=reference_date,
            )

    row_dates = dates.loc[matched_rows.index]
    date_missing_count = int(row_dates.isna().sum())
    if date_missing_count:
        flags.append("missing_sample_dates")
    valid_dates = row_dates.dropna()
    earliest_date, latest_date, record_age_days = None, None, None
    if not valid_dates.empty:
        earliest_date = valid_dates.min().date().isoformat()
        latest = valid_dates.max()
        latest_date = latest.date().isoformat()
        record_age_days = int((reference - latest.normalize()).days)
        if record_age_days > STALE_AFTER_DAYS:
            flags.append("stale_record")
        if record_age_days < 0:
            flags.append("sample_date_after_reference")
    else:
        flags.append("sample_date_unavailable")
    if matched_column.casefold() == "district":
        flags.append("district_level_match")

    parameters: dict[str, Any] = {}
    trace_metal_zero_values: list[dict[str, Any]] = []
    for col in present_measurements:
        series = matched_rows[col].replace(r"^\s*-\s*$", pd.NA, regex=True)
        missing_count = int(series.isna().sum())
        numeric = pd.to_numeric(series, errors="coerce")
        finite_mask = numeric.map(lambda value: pd.notna(value) and math.isfinite(float(value)))
        valid = numeric[finite_mask]
        is_categorical = col.strip().casefold() in {"colour", "odour"}
        valid_measurement_mask = series.notna() if is_categorical else finite_mask
        measurement_count = int(valid_measurement_mask.sum())
        measurement_valid_dates = row_dates.loc[valid_measurement_mask].dropna()
        measurement_date_missing_count = int((valid_measurement_mask & row_dates.isna()).sum())
        measurement_flags: list[str] = []
        latest_measurement_date = None
        measurement_age_days = None
        stale_measurement = None
        if measurement_count == 0:
            measurement_status = "no_valid_measurements"
            measurement_flags.append("no_valid_measurements")
        elif measurement_valid_dates.empty:
            measurement_status = "measurement_date_unavailable"
            measurement_flags.append("measurement_date_unavailable")
        else:
            latest_measurement = measurement_valid_dates.max()
            latest_measurement_date = latest_measurement.date().isoformat()
            measurement_age_days = int((reference - latest_measurement.normalize()).days)
            if measurement_date_missing_count:
                measurement_status = "partial_measurement_dates"
                measurement_flags.append("measurement_dates_missing")
            else:
                measurement_status = "available"
                stale_measurement = measurement_age_days > STALE_AFTER_DAYS
            if stale_measurement is True:
                measurement_flags.append("stale_measurement")
            if measurement_age_days < 0:
                measurement_flags.append("measurement_after_reference")
        if not is_categorical:
            missing_count = int((~finite_mask).sum())
        zero_count = int((valid == 0).sum()) if not is_categorical else None
        if col.strip().casefold() in TRACE_METAL_PARAMETER_NAMES and zero_count:
            trace_metal_zero_values.append({"parameter": col, "zero_count": zero_count})
        parameters[col] = {
            "unit": _unit_from_name(col),
            "measurement_count": int(series.notna().sum()) if is_categorical else int(valid.size),
            "missing_count": missing_count,
            "zero_count": zero_count,
            "latest_measurement_date": latest_measurement_date,
            "measurement_age_days": measurement_age_days,
            "stale_measurement": stale_measurement,
            "measurement_status": measurement_status,
            "measurement_date_missing_count": measurement_date_missing_count,
            "measurement_quality_flags": measurement_flags,
            "mean": _finite_number(valid.mean()) if not valid.empty else None,
            "median": _finite_number(valid.median()) if not valid.empty else None,
            "min": _finite_number(valid.min()) if not valid.empty else None,
            "max": _finite_number(valid.max()) if not valid.empty else None,
            "std": _finite_number(valid.std()) if valid.size > 1 else None,
            "observed_categories": (
                {str(k): int(v) for k, v in series.dropna().astype(str).value_counts().items()}
                if is_categorical else None
            ),
        }
    if not present_measurements:
        flags.append("no_measurement_columns")
    if trace_metal_zero_values:
        flags.append("trace_metal_zero_values_unverified")

    return {
        "source_type": source_type, "dataset_agency": SOURCE_DATASETS[source_type],
        "requested_location": requested, "match_level": matched_column.casefold(),
        "matched_column": matched_column, "sample_count": int(len(matched_rows)),
        "candidate_sample_count": int(len(matched_rows)),
        "earliest_sample_date": earliest_date, "latest_sample_date": latest_date,
        "record_age_days": record_age_days,
        "date_column": date_col, "reference_date": reference_date,
        "date_missing_count": date_missing_count, "parameters": parameters,
        "zero_value_diagnostics": {
            "trace_metal_parameters_with_zero_values": trace_metal_zero_values,
            "caution": ZERO_VALUE_CAUTION,
        },
        "ambiguous_candidates": [], "measurement_columns_present": present_measurements,
        "measurement_columns_missing": missing_measurements, "data_quality_flags": flags,
        "geographic_proximity_established": False, "historical_data_only": True,
    }
