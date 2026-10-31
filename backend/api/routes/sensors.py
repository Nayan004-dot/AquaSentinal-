from __future__ import annotations

import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status

from backend.database import session
from backend.schemas import OutletTelemetry
from backend.services.ingestion import DuplicateSampleError, store_sample

router = APIRouter(prefix="/sensors", tags=["sensor-ingestion"])


@router.post("/outlet", status_code=status.HTTP_201_CREATED)
def ingest_outlet(payload: OutletTelemetry, request: Request,
                  x_device_token: str | None = Header(default=None, alias="X-Device-Token")):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")
    settings = request.app.state.settings
    expected = settings.device_tokens.get(payload.device_id)
    if not expected or not x_device_token or not hmac.compare_digest(expected, x_device_token):
        raise HTTPException(status_code=401, detail="Missing or invalid device token")
    received_at = datetime.now(timezone.utc)
    db_path = settings.resolved_database_path()
    with session(db_path) as conn:
        try:
            return store_sample(conn, payload, received_at)
        except DuplicateSampleError:
            raise HTTPException(status_code=409, detail={
                "accepted": False, "duplicate": True,
                "message": "This device_id and sequence pair has already been accepted",
                "device_id": payload.device_id, "sequence": payload.sequence,
            })
