from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request

from backend.database import session

router = APIRouter(prefix="/device", tags=["devices"])


@router.get("/status")
def device_status(request: Request, device_id: str = Query(min_length=1, max_length=80)):
    settings = request.app.state.settings
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat(timespec="microseconds").replace("+00:00", "Z")
    with session(settings.resolved_database_path()) as conn:
        latest = conn.execute(
            "SELECT * FROM telemetry_samples WHERE device_id = ? ORDER BY received_at DESC, id DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        counts = conn.execute(
            "SELECT event_type, COUNT(*) AS count FROM ingestion_events WHERE device_id = ? AND occurred_at >= ? GROUP BY event_type",
            (device_id, since),
        ).fetchall()
        invalid = conn.execute(
            "SELECT measurements_json FROM telemetry_samples WHERE device_id = ? AND received_at >= ?",
            (device_id, since),
        ).fetchall()
    event_counts = {row["event_type"]: row["count"] for row in counts}
    invalid_measurements = 0
    for row in invalid:
        import json
        values = json.loads(row["measurements_json"])
        invalid_measurements += sum(1 for item in values.values() if item["status"] != "valid")
    if latest is None:
        return {"device_id": device_id, "status": "no_data", "last_captured_at": None,
                "last_received_at": None, "last_sequence": None, "firmware_version": None,
                "accepted_samples_24h": event_counts.get("accepted", 0),
                "duplicate_submissions_24h": event_counts.get("duplicate", 0),
                "non_valid_measurements_24h": invalid_measurements}
    received = datetime.fromisoformat(latest["received_at"].replace("Z", "+00:00"))
    age = max(0, (now - received).total_seconds())
    return {"device_id": device_id, "status": "online" if age <= settings.device_stale_after_seconds else "stale",
            "last_captured_at": latest["captured_at"], "last_received_at": latest["received_at"],
            "last_sequence": latest["sequence"], "firmware_version": latest["firmware_version"],
            "age_seconds": round(age, 2), "stale_after_seconds": settings.device_stale_after_seconds,
            "accepted_samples_24h": event_counts.get("accepted", 0),
            "duplicate_submissions_24h": event_counts.get("duplicate", 0),
            "non_valid_measurements_24h": invalid_measurements,
            "connectivity_note": "Status is inferred from received telemetry; it is not a direct Wi-Fi signal measurement."}
