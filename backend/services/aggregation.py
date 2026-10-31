from __future__ import annotations

import json
import math
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config import Settings
from backend.services.ingestion import iso_utc

PARAMETERS = {
    "tds": "ppm", "ph": "pH", "turbidity": None, "temperature": "C"
}


def floor_half_hour(value: datetime) -> datetime:
    value = value.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return value.replace(minute=(value.minute // 30) * 30)


def _percent(numerator: int, denominator: int) -> float:
    return round((min(numerator, denominator) / denominator) * 100.0, 2) if denominator else 0.0


def aggregate_window(conn: sqlite3.Connection, device_id: str, start: datetime, settings: Settings,
                     now: datetime | None = None) -> dict[str, Any]:
    start = start.astimezone(timezone.utc)
    end = start + timedelta(minutes=30)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if end + timedelta(seconds=settings.aggregation_late_arrival_seconds) > now:
        raise ValueError("Cannot aggregate a window before its close and late-arrival allowance")
    rows = conn.execute(
        "SELECT measurements_json FROM telemetry_samples WHERE device_id = ? AND captured_at >= ? AND captured_at < ? ORDER BY captured_at, id",
        (device_id, iso_utc(start), iso_utc(end)),
    ).fetchall()
    expected = math.ceil(1800 / settings.sampling_interval_seconds)
    parameters: dict[str, Any] = {}
    for name, default_unit in PARAMETERS.items():
        values: list[float] = []
        received_count = invalid_count = uncalibrated_count = 0
        unit = default_unit
        for row in rows:
            measurement = json.loads(row["measurements_json"])[name]
            unit = measurement.get("unit") or unit
            value = measurement.get("value")
            status = measurement.get("status")
            calibrated = measurement.get("calibrated") is True
            if value is not None:
                received_count += 1
            if status == "invalid":
                invalid_count += 1
            if status == "valid" and value is not None and not calibrated:
                uncalibrated_count += 1
            if status == "valid" and value is not None and calibrated:
                values.append(float(value))
        missing_count = max(expected - received_count, 0)
        valid_count = len(values)
        received_coverage = _percent(received_count, expected)
        valid_coverage = _percent(valid_count, expected)
        usable = valid_count > 0 and valid_count / expected >= settings.aggregation_min_valid_coverage
        parameters[name] = {
            "unit": unit, "expected_count": expected, "received_count": received_count,
            "valid_count": valid_count, "invalid_count": invalid_count,
            "uncalibrated_count": uncalibrated_count, "missing_count": missing_count,
            "received_coverage_percent": received_coverage,
            "valid_coverage_percent": valid_coverage,
            "coverage_percent": valid_coverage,
            "mean": round(statistics.fmean(values), 4) if values else None,
            "median": round(statistics.median(values), 4) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "standard_deviation": round(statistics.stdev(values), 4) if len(values) > 1 else None,
            "usable": usable,
        }
    generated = iso_utc(now)
    result = {"device_id": device_id, "window_type": "30m", "window_start": iso_utc(start),
              "window_end": iso_utc(end), "status": "completed" if rows else "completed_no_samples",
              "sample_count": len(rows), "sampling_interval_seconds": settings.sampling_interval_seconds,
              "minimum_valid_coverage_percent": round(settings.aggregation_min_valid_coverage * 100, 2),
              "parameters": parameters, "generated_at": generated}
    conn.execute(
        """INSERT INTO outlet_summaries(device_id, window_start, window_end, summary_json, generated_at)
        VALUES (?, ?, ?, ?, ?) ON CONFLICT(device_id, window_start, window_end)
        DO UPDATE SET summary_json=excluded.summary_json, generated_at=excluded.generated_at""",
        (device_id, iso_utc(start), iso_utc(end), json.dumps(result, allow_nan=False), generated),
    )
    conn.commit()
    return result


def aggregate_closed_windows(conn: sqlite3.Connection, settings: Settings,
                             now: datetime | None = None) -> int:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(seconds=settings.aggregation_late_arrival_seconds)
    rows = conn.execute(
        "SELECT DISTINCT device_id, captured_at FROM telemetry_samples WHERE captured_at < ? ORDER BY device_id, captured_at",
        (iso_utc(cutoff),),
    ).fetchall()
    windows: set[tuple[str, datetime]] = set()
    for row in rows:
        captured = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00"))
        start = floor_half_hour(captured)
        if start + timedelta(minutes=30, seconds=settings.aggregation_late_arrival_seconds) <= now:
            windows.add((row["device_id"], start))
    count = 0
    for device_id, start in windows:
        aggregate_window(conn, device_id, start, settings, now)
        count += 1
    return count
