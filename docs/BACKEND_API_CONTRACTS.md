# AquaSentinel Backend API Contracts — V1

Base path: `/api/v1`.

All timestamps must be ISO 8601 with timezone information. Backend storage and aggregation use UTC. Responses include timestamps in ISO 8601 UTC (`Z`) unless otherwise documented. `null` means unavailable; it never means zero.

## 1. Health

`GET /api/v1/health`

Example response:

```json
{
  "status": "ok",
  "service": "aquasentinel-backend",
  "api_version": "v1"
}
```

Do not include secrets, database credentials or internal filesystem paths.

## 2. ESP32 telemetry ingestion

`POST /api/v1/sensors/outlet`

Authentication: device-specific token in `X-Device-Token` header. Never place the token in the JSON body or firmware source committed to Git. Provision it privately.

Request:

```json
{
  "schema_version": "1.0",
  "device_id": "AQUASENTINEL-01",
  "sequence": 1025,
  "timestamp": "2026-11-01T10:30:10+05:30",
  "measurement_point": "outlet",
  "firmware_version": "0.1.0",
  "outlet": {
    "tds": {"value": 180.5, "unit": "ppm", "status": "valid", "calibrated": true},
    "ph": {"value": 7.1, "unit": "pH", "status": "valid", "calibrated": true},
    "turbidity": {"value": 0.8, "unit": "NTU", "status": "valid", "calibrated": true},
    "temperature": {"value": 26.5, "unit": "C", "status": "valid", "calibrated": true}
  }
}
```

All values above are examples, not recommended water-quality targets. Turbidity may use `NTU` only where calibration supports that unit; otherwise use `raw`. A measurement may have `value: null` when status is `invalid`, `disconnected`, `warming_up` or `unavailable`. A null value must never be converted to zero.

Successful response (first accepted sample):

```json
{
  "accepted": true,
  "duplicate": false,
  "device_id": "AQUASENTINEL-01",
  "sequence": 1025,
  "captured_at": "2026-11-01T05:00:10Z",
  "received_at": "2026-11-01T05:00:11Z"
}
```

A repeated `(device_id, sequence)` must not be inserted twice. Backend should return a documented duplicate response (for example, HTTP 409 with `duplicate: true`) and must not re-aggregate it as a new sample.

Recommended error behavior:

| HTTP status | Meaning |
|---|---|
| 400 | Malformed request or unsupported schema version |
| 401 / 403 | Missing or invalid device authentication |
| 409 | Duplicate sequence/sample conflict |
| 413 | Payload too large |
| 422 | Schema, type, unit or timestamp validation failed |
| 429 | Rate limit exceeded |
| 500 / 503 | Temporary backend/storage/service failure |

The exact error JSON should be consistent and documented.

## 3. Latest outlet readings

`GET /api/v1/outlet/latest?device_id=AQUASENTINEL-01`

Example response:

```json
{
  "device_id": "AQUASENTINEL-01",
  "measurement_point": "outlet",
  "captured_at": "2026-11-01T05:00:10Z",
  "received_at": "2026-11-01T05:00:11Z",
  "measurements": {
    "tds": {"value": 180.5, "unit": "ppm", "status": "valid", "calibrated": true},
    "ph": {"value": 7.1, "unit": "pH", "status": "valid", "calibrated": true},
    "turbidity": {"value": 0.8, "unit": "NTU", "status": "valid", "calibrated": true},
    "temperature": {"value": 26.5, "unit": "C", "status": "valid", "calibrated": true}
  },
  "data_status": "available"
}
```

When no reading exists, return `data_status: "no_data"` and explicit null fields or an empty measurement object. Do not return zero placeholders.

## 4. Outlet history

`GET /api/v1/outlet/history?device_id=AQUASENTINEL-01&from=2026-11-01T00:00:00Z&to=2026-11-01T01:00:00Z&parameter=tds&limit=500`

- `from` and `to` are required ISO 8601 timestamps with timezone.
- `parameter` is optional: `tds`, `ph`, `turbidity` or `temperature`.
- Enforce a maximum time span and page size.
- Return records in ascending or descending order consistently and document it.
- Include `next_cursor` or another documented pagination mechanism.
- Preserve gaps; never fill missing samples with zeros.

Example response:

```json
{
  "device_id": "AQUASENTINEL-01",
  "parameter": "tds",
  "unit": "ppm",
  "items": [
    {"captured_at": "2026-11-01T05:00:10Z", "received_at": "2026-11-01T05:00:11Z", "value": 180.5, "status": "valid", "calibrated": true}
  ],
  "next_cursor": null
}
```

## 5. Completed 30-minute summary

`GET /api/v1/outlet/summary?device_id=AQUASENTINEL-01&window=30m&limit=24`

Use fixed UTC windows: `[hh:00, hh:30)` and `[hh:30, next hh:00)`. Only return completed windows. A separate `status` identifies incomplete/insufficient windows if the implementation chooses to expose them.

Example response:

```json
{
  "device_id": "AQUASENTINEL-01",
  "window_type": "30m",
  "window_start": "2026-11-01T04:30:00Z",
  "window_end": "2026-11-01T05:00:00Z",
  "status": "completed",
  "sampling_interval_seconds": 10,
  "parameters": {
    "tds": {
      "unit": "ppm",
      "expected_count": 180,
      "received_count": 178,
      "valid_count": 175,
      "invalid_count": 2,
      "uncalibrated_count": 1,
      "missing_count": 2,
      "coverage_percent": 98.9,
      "mean": 182.4,
      "median": 181.0,
      "minimum": 175.0,
      "maximum": 190.0,
      "standard_deviation": 4.5
    }
  },
  "generated_at": "2026-11-01T05:00:05Z"
}
```

The numbers are illustrative. The implementation must define coverage precisely (for example, received/expected and valid/expected), preferably returning both so the UI can distinguish transport completeness from valid-data completeness. The example's `coverage_percent` should have a documented denominator. Per-parameter statistics must be computed only from eligible readings; report invalid and uncalibrated records separately. The backend must use a configurable minimum coverage rule before declaring a summary usable.

Initial target: 10-second sampling, which gives a nominal 180 expected samples per parameter in 30 minutes. Sampling frequency is configurable and expected count must be calculated from the configured interval, not hardcoded.

## 6. Device status

`GET /api/v1/device/status?device_id=AQUASENTINEL-01`

Return:
- device ID and firmware version (if available)
- most recent capture timestamp
- most recent backend receipt timestamp
- freshness/connection state based on a documented timeout
- last sequence number
- accepted, invalid and duplicate counts over a defined period

Connection state is inferred from recent received telemetry; it is not a direct Wi-Fi signal measurement.

## 7. Historical-context integration boundary (later integration)

Person 1 owns the existing historical-context module. The backend can later expose:

- `GET /api/v1/locations?source_type=groundwater`
- `GET /api/v1/historical-context?source_type=groundwater&location_id=...`

These routes must call the existing historical-context implementation through a stable adapter provided/approved by Person 1. Do not reimplement the CSV analysis in the frontend or duplicate the historical module in the backend. Do not claim these endpoints are implemented until tested against the actual module.

## 8. Not in V1

Do not implement fake `/filter-health` or `/decision` responses. Those endpoints are future work after their methods and criteria are validated. Dashboard should show R&D-in-progress placeholders until then.
