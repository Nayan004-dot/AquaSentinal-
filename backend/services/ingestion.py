from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.schemas import OutletTelemetry


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def store_sample(conn: sqlite3.Connection, payload: OutletTelemetry, received_at: datetime) -> dict[str, Any]:
    captured_at = iso_utc(payload.timestamp)
    received = iso_utc(received_at)
    prior = conn.execute(
        "SELECT MAX(sequence) AS max_sequence FROM telemetry_samples WHERE device_id = ?",
        (payload.device_id,),
    ).fetchone()["max_sequence"]
    flags = ["out_of_order_sequence"] if prior is not None and payload.sequence < prior else []
    measurements = payload.outlet.model_dump(mode="json")
    try:
        cursor = conn.execute(
            """INSERT INTO telemetry_samples
            (device_id, sequence, captured_at, received_at, measurement_point,
             firmware_version, measurements_json, ingestion_flags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.device_id, payload.sequence, captured_at, received, payload.measurement_point,
             payload.firmware_version, json.dumps(measurements, allow_nan=False), json.dumps(flags)),
        )
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" in str(exc).upper():
            conn.execute(
                "INSERT INTO ingestion_events(device_id, sequence, event_type, occurred_at) VALUES (?, ?, 'duplicate', ?)",
                (payload.device_id, payload.sequence, received),
            )
            conn.commit()
            raise DuplicateSampleError from exc
        raise
    conn.execute(
        "INSERT INTO ingestion_events(device_id, sequence, event_type, occurred_at) VALUES (?, ?, 'accepted', ?)",
        (payload.device_id, payload.sequence, received),
    )
    conn.commit()
    return {"accepted": True, "duplicate": False, "device_id": payload.device_id,
            "sequence": payload.sequence, "captured_at": captured_at, "received_at": received,
            "sample_id": cursor.lastrowid, "ingestion_flags": flags}


class DuplicateSampleError(Exception):
    pass
