from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app

DEVICE_ID = "AQUASENTINEL-01"
TOKEN = "test-device-secret-not-for-production"


def make_client(tmp_path, **overrides):
    settings = Settings(
        database_path=str(tmp_path / "test.sqlite3"),
        device_tokens={DEVICE_ID: TOKEN},
        sampling_interval_seconds=10,
        device_stale_after_seconds=120,
        aggregation_late_arrival_seconds=0,
        aggregation_min_valid_coverage=0.0,
        aggregation_poll_seconds=60,
        **overrides,
    )
    app = create_app(settings, start_aggregation_worker=False)
    return TestClient(app)


def payload(sequence=1, timestamp="2024-01-01T00:05:00+00:00"):
    return {
        "schema_version": "1.0",
        "device_id": DEVICE_ID,
        "sequence": sequence,
        "timestamp": timestamp,
        "measurement_point": "outlet",
        "firmware_version": "test-0.1",
        "outlet": {
            "tds": {"value": 180.5, "unit": "ppm", "status": "valid", "calibrated": True},
            "ph": {"value": 7.1, "unit": "pH", "status": "valid", "calibrated": True},
            "turbidity": {"value": 0.8, "unit": "NTU", "status": "valid", "calibrated": True},
            "temperature": {"value": 26.5, "unit": "C", "status": "valid", "calibrated": True},
        },
    }


def test_health_and_no_data(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/api/v1/health").json() == {
            "status": "ok", "service": "aquasentinel-backend", "api_version": "v1"
        }
        response = client.get("/api/v1/outlet/latest", params={"device_id": DEVICE_ID})
        assert response.status_code == 200
        assert response.json()["data_status"] == "no_data"
        assert response.json()["measurements"] == {}


def test_ingest_requires_device_token_and_stores_sample(tmp_path):
    with make_client(tmp_path) as client:
        body = payload()
        assert client.post("/api/v1/sensors/outlet", json=body).status_code == 401
        response = client.post("/api/v1/sensors/outlet", json=body,
                               headers={"X-Device-Token": TOKEN})
        assert response.status_code == 201
        result = response.json()
        assert result["accepted"] is True
        assert result["sequence"] == 1
        latest = client.get("/api/v1/outlet/latest", params={"device_id": DEVICE_ID}).json()
        assert latest["measurements"]["tds"]["value"] == 180.5


def test_duplicate_sequence_is_rejected_and_not_duplicated(tmp_path):
    with make_client(tmp_path) as client:
        headers = {"X-Device-Token": TOKEN}
        first = client.post("/api/v1/sensors/outlet", json=payload(), headers=headers)
        second = client.post("/api/v1/sensors/outlet", json=payload(), headers=headers)
        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json()["detail"]["duplicate"] is True
        history = client.get("/api/v1/outlet/history", params={
            "device_id": DEVICE_ID, "from": "2024-01-01T00:00:00Z",
            "to": "2024-01-01T00:30:00Z"
        }).json()
        assert len(history["items"]) == 1


def test_invalid_timestamp_without_timezone_is_rejected(tmp_path):
    with make_client(tmp_path) as client:
        body = payload(timestamp="2024-01-01T00:05:00")
        response = client.post("/api/v1/sensors/outlet", json=body,
                               headers={"X-Device-Token": TOKEN})
        assert response.status_code == 422


def test_null_measurement_is_not_converted_to_zero(tmp_path):
    with make_client(tmp_path) as client:
        body = payload()
        body["outlet"]["tds"] = {
            "value": None, "unit": "ppm", "status": "disconnected", "calibrated": False
        }
        response = client.post("/api/v1/sensors/outlet", json=body,
                               headers={"X-Device-Token": TOKEN})
        assert response.status_code == 201
        latest = client.get("/api/v1/outlet/latest", params={"device_id": DEVICE_ID}).json()
        assert latest["measurements"]["tds"]["value"] is None


def test_half_hour_summary_is_created_and_idempotent(tmp_path):
    with make_client(tmp_path) as client:
        headers = {"X-Device-Token": TOKEN}
        for seq, minute in enumerate((1, 5, 10), start=1):
            body = payload(seq, f"2024-01-01T00:{minute:02d}:00+00:00")
            body["outlet"]["tds"]["value"] = 100 + seq
            response = client.post("/api/v1/sensors/outlet", json=body, headers=headers)
            assert response.status_code == 201
        result = client.get("/api/v1/outlet/summary", params={"device_id": DEVICE_ID}).json()
        assert len(result["items"]) == 1
        summary = result["items"][0]
        tds = summary["parameters"]["tds"]
        assert tds["valid_count"] == 3
        assert tds["mean"] == 102.0
        assert tds["expected_count"] == 180
        assert tds["missing_count"] == 177
        # A subsequent call updates the same persisted window, not a second row.
        client.get("/api/v1/outlet/summary", params={"device_id": DEVICE_ID})
        assert len(client.get("/api/v1/outlet/summary", params={"device_id": DEVICE_ID}).json()["items"]) == 1


def test_history_requires_aware_dates_and_valid_range(tmp_path):
    with make_client(tmp_path) as client:
        missing_tz = client.get("/api/v1/outlet/history", params={
            "device_id": DEVICE_ID, "from": "2024-01-01T00:00:00",
            "to": "2024-01-01T01:00:00Z"
        })
        assert missing_tz.status_code == 422
        reversed_range = client.get("/api/v1/outlet/history", params={
            "device_id": DEVICE_ID, "from": "2024-01-02T00:00:00Z",
            "to": "2024-01-01T00:00:00Z"
        })
        assert reversed_range.status_code == 422


def test_ingestion_requires_json_content_type(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post("/api/v1/sensors/outlet", content="{}",
                               headers={"X-Device-Token": TOKEN, "Content-Type": "text/plain"})
        assert response.status_code == 415


def test_ingestion_rejects_oversized_content_length(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post("/api/v1/sensors/outlet", content="{}",
                               headers={"X-Device-Token": TOKEN, "Content-Type": "application/json",
                                        "Content-Length": "9000"})
        assert response.status_code == 413
