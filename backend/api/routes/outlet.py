from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from backend.database import session
from backend.services.aggregation import aggregate_closed_windows
from backend.services.ingestion import iso_utc

router = APIRouter(prefix="/outlet", tags=["outlet-data"])
PARAMETERS = {"tds", "ph", "turbidity", "temperature"}
UNITS = {"tds": "ppm", "ph": "pH", "turbidity": None, "temperature": "C"}


def _aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(status_code=422, detail=f"{name} must include a timezone offset or Z")
    return value.astimezone(timezone.utc)


def _encode_cursor(captured_at: str, row_id: int) -> str:
    raw = json.dumps([captured_at, row_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        value = json.loads(raw)
        if not isinstance(value, list) or len(value) != 2 or not isinstance(value[0], str) or not isinstance(value[1], int):
            raise ValueError
        return value[0], value[1]
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid history cursor") from exc


@router.get("/latest")
def latest_outlet(request: Request, device_id: str = Query(min_length=1, max_length=80)):
    settings = request.app.state.settings
    with session(settings.resolved_database_path()) as conn:
        row = conn.execute(
            "SELECT * FROM telemetry_samples WHERE device_id = ? ORDER BY captured_at DESC, id DESC LIMIT 1",
            (device_id,),
        ).fetchone()
    if row is None:
        return {"device_id": device_id, "measurement_point": "outlet", "captured_at": None,
                "received_at": None, "measurements": {}, "data_status": "no_data"}
    received = datetime.fromisoformat(row["received_at"].replace("Z", "+00:00"))
    age = max(0.0, (datetime.now(timezone.utc) - received).total_seconds())
    return {"device_id": device_id, "measurement_point": row["measurement_point"],
            "captured_at": row["captured_at"], "received_at": row["received_at"],
            "measurements": json.loads(row["measurements_json"]),
            "ingestion_flags": json.loads(row["ingestion_flags_json"]),
            "data_status": "stale" if age > settings.device_stale_after_seconds else "available",
            "age_seconds": round(age, 2)}


@router.get("/history")
def outlet_history(
    request: Request,
    device_id: str = Query(min_length=1, max_length=80),
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    parameter: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    cursor: str | None = Query(default=None),
):
    settings = request.app.state.settings
    start, end = _aware(from_, "from"), _aware(to, "to")
    if start >= end:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    if (end - start).total_seconds() > settings.max_history_days * 86400:
        raise HTTPException(status_code=422, detail=f"History range cannot exceed {settings.max_history_days} days")
    if parameter is not None and parameter not in PARAMETERS:
        raise HTTPException(status_code=422, detail=f"parameter must be one of {sorted(PARAMETERS)}")
    page_size = limit or settings.default_history_limit
    if page_size > settings.max_history_limit:
        raise HTTPException(status_code=422, detail=f"limit cannot exceed {settings.max_history_limit}")
    sql = "SELECT * FROM telemetry_samples WHERE device_id = ? AND captured_at >= ? AND captured_at < ?"
    args: list[object] = [device_id, iso_utc(start), iso_utc(end)]
    if cursor:
        cursor_time, cursor_id = _decode_cursor(cursor)
        sql += " AND (captured_at > ? OR (captured_at = ? AND id > ?))"
        args.extend([cursor_time, cursor_time, cursor_id])
    sql += " ORDER BY captured_at ASC, id ASC LIMIT ?"
    args.append(page_size + 1)
    with session(settings.resolved_database_path()) as conn:
        rows = conn.execute(sql, args).fetchall()
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    items = []
    for row in rows:
        measurements = json.loads(row["measurements_json"])
        base = {"captured_at": row["captured_at"], "received_at": row["received_at"],
                "sequence": row["sequence"], "ingestion_flags": json.loads(row["ingestion_flags_json"])}
        if parameter:
            measurement = measurements[parameter]
            base.update({"value": measurement["value"], "unit": measurement["unit"],
                         "status": measurement["status"], "calibrated": measurement["calibrated"]})
        else:
            base["measurements"] = measurements
        items.append(base)
    next_cursor = _encode_cursor(rows[-1]["captured_at"], rows[-1]["id"]) if has_more and rows else None
    return {"device_id": device_id, "parameter": parameter,
            "unit": UNITS.get(parameter) if parameter else None,
            "items": items, "next_cursor": next_cursor,
            "order": "captured_at_ascending"}


@router.get("/summary")
def outlet_summary(request: Request, device_id: str = Query(min_length=1, max_length=80),
                   window: str = Query(default="30m", pattern="^30m$"),
                   limit: int = Query(default=24, ge=1, le=500)):
    settings = request.app.state.settings
    with session(settings.resolved_database_path()) as conn:
        aggregate_closed_windows(conn, settings)
        rows = conn.execute(
            "SELECT summary_json FROM outlet_summaries WHERE device_id = ? ORDER BY window_start DESC LIMIT ?",
            (device_id, limit),
        ).fetchall()
    return {"device_id": device_id, "window_type": "30m",
            "window_convention": "UTC fixed half-hour windows [hh:00,hh:30) and [hh:30,next hh:00)",
            "items": [json.loads(row["summary_json"]) for row in rows]}
