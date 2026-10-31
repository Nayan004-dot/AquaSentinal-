# AquaSentinel API Contracts (V1)

These are the agreed interface drafts for parallel work. Person 1 implements the backend contract; Person 2 implements compatible ESP32 telemetry; Person 3 consumes the GET endpoints. Keep timestamps ISO 8601 with timezone offsets. Treat null as unavailable, never as zero.

## 1. List locations

`GET /api/v1/locations?source_type=groundwater`

`source_type` is `groundwater` or `surface_water`.

Example response:

```json
{
  "source_type": "groundwater",
  "items": [
    {
      "location_id": "kadipur",
      "label": "Kadipur",
      "match_fields": ["Station", "Village"],
      "match_level_available": "station"
    }
  ]
}
```

Only return locations actually available in the corresponding dataset. Do not imply complete coverage of every place in Uttar Pradesh.

## 2. Retrieve historical context

`GET /api/v1/historical-context?source_type=groundwater&location_id=kadipur`

The backend calls the existing historical-context module. The response should retain its actual source-derived fields, including where available:

- `source_type`, `dataset_agency`, `requested_location`
- match result/level/field and ambiguous candidates
- observation and candidate counts
- earliest/latest station sample dates
- parameter-specific statistics and original units
- per-parameter latest valid measurement date and age
- valid/missing counts
- stale and other quality flags
- provenance and scientific limitations

Example normalized shape for frontend consumption (illustrative contract only; map from the actual module output):

```json
{
  "source_type": "groundwater",
  "dataset_agency": "CGWB",
  "requested_location": "Kadipur",
  "match": {
    "status": "matched",
    "level": "station",
    "field": "Station"
  },
  "sample_count": 9,
  "earliest_sample_date": "2000-05-25",
  "latest_station_sample_date": "2021-05-30",
  "parameters": {
    "tds": {
      "original_name": "Total Dissolved Solids",
      "unit": "mg/L",
      "valid_count": 0,
      "missing_count": 9,
      "mean": null,
      "median": null,
      "minimum": null,
      "maximum": null,
      "latest_valid_measurement_date": null,
      "age_days": null,
      "stale": null,
      "quality_flags": []
    }
  },
  "data_quality_flags": [],
  "limitations": ["Historical observations are not live inlet readings."]
}
```

The example is not a claim about current live data. Actual parameter values must come from the selected query. Do not merge dates across parameters.

## 3. ESP32 outlet telemetry ingestion

`POST /api/v1/sensors/outlet`

Person 2 sends one telemetry sample per request. Initial target interval is 10 seconds, configurable after sensor testing.

Example request:

```json
{
  "device_id": "AQUASENTINEL-01",
  "sequence": 1025,
  "timestamp": "2026-11-01T10:30:00+05:30",
  "measurement_point": "outlet",
  "outlet": {
    "tds": {"value": 180, "unit": "ppm", "status": "valid", "calibrated": true},
    "ph": {"value": 7.1, "unit": "pH", "status": "valid", "calibrated": true},
    "turbidity": {"value": 0.8, "unit": "NTU", "status": "valid", "calibrated": true},
    "temperature": {"value": 26.5, "unit": "C", "status": "valid", "calibrated": true}
  },
  "firmware_version": "0.1.0"
}
```

Values are illustrative. Turbidity may be labelled NTU only if calibration supports that unit. The timestamp must represent the device measurement time; backend must independently record `received_at`. `sequence` should increase monotonically per device to help identify duplicates or gaps. A missing sensor value is `null` with an appropriate status, never `0` as a placeholder.

Example successful response:

```json
{
  "accepted": true,
  "device_id": "AQUASENTINEL-01",
  "sequence": 1025,
  "received_at": "2026-11-01T05:00:01Z"
}
```

Backend should authenticate the device, validate schema and units, reject or quarantine malformed/out-of-range payloads, detect duplicate sequence values, and avoid storing credentials in records.

## 4. Latest outlet reading

`GET /api/v1/outlet/latest?device_id=AQUASENTINEL-01`

Return the latest accepted reading per sensor, its measurement timestamp, server receipt timestamp, validity/calibration state and device freshness. Return explicit null/no-data status when no valid reading exists.

## 5. Outlet history

`GET /api/v1/outlet/history?device_id=AQUASENTINEL-01&from=...&to=...`

Return timestamped raw or appropriately downsampled records for charts. Document pagination and limits. Frontend must not assume missing intervals are zero readings.

## 6. Completed 30-minute summary

`GET /api/v1/outlet/summary?device_id=AQUASENTINEL-01&window=30m`

Summaries are calculated by the backend after a fixed 30-minute window closes. Return:

- window start and end
- expected sample count (based on configured sampling interval)
- received, valid, invalid and missing counts per parameter
- data coverage percentage per parameter
- mean, median, min, max and standard deviation per parameter, when sufficient valid readings exist
- calibration/quality flags
- completion status

With an initial 10-second sampling interval, a full 30-minute window would contain 180 expected samples per sensor. This is an expected count, not a guarantee. Do not publish a completed summary before the window closes or if minimum-coverage requirements are not met. Keep the raw data after summarization.

## 7. Device status

`GET /api/v1/device/status?device_id=AQUASENTINEL-01`

Return last device timestamp, last backend receipt time, connectivity/freshness status, firmware version and recent accepted/rejected sample counts.

## 8. Future endpoints (not V1 functionality)

Potential future endpoints:

- `GET /api/v1/filter-performance?device_id=...&period=7d`
- `GET /api/v1/decision?device_id=...`

These must remain unimplemented or clearly disabled until Person 1 has implemented and validated filter-performance and decision logic. Do not fabricate responses for the dashboard.

## 9. Dashboard refresh guidance

- Historical context: fetch after source/location selection or dataset refresh; not every 30 minutes.
- Latest outlet readings: poll approximately every 5–10 seconds initially.
- Completed 30-minute summaries: fetch after a window closes, or poll at a low frequency for a new completed summary.
- Filter performance: future feature; derive from actual stored trends and service records.

## 10. Networking and security

- Development can use laptop LAN IP while devices share a network.
- Remote prototype path: public HTTPS URL through a secure tunnel to Person 1's laptop-hosted FastAPI service.
- ESP32 and dashboard do not need the same Wi-Fi when the public HTTPS route is available.
- Laptop, backend and tunnel must be online.
- Require device-specific authentication for POST telemetry. Use HTTPS, validation, rate limits and restricted CORS. Never commit tokens or Wi-Fi credentials.
