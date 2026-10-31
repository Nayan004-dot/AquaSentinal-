# AquaSentinel Backend API Contracts — V1 implementation

Base path: `/api/v1`. All timestamps must include a timezone. Input timestamps are normalized to UTC for storage; response timestamps use UTC `Z`.

## Device authentication

`POST /sensors/outlet` requires `X-Device-Token`, provisioned privately and mapped to the exact `device_id` in server environment configuration. No device tokens belong in request JSON, frontend code or Git.

## Ingestion

`POST /api/v1/sensors/outlet` accepts the JSON schema in [`../contracts/outlet_sensor_telemetry.schema.json`](../contracts/outlet_sensor_telemetry.schema.json).

- `201`: accepted and saved.
- `401`: missing/invalid token.
- `409`: duplicate `(device_id, sequence)`; not saved again.
- `422`: schema/value/unit/timestamp validation failure.

The API records both `timestamp` (device capture time, stored as `captured_at`) and server `received_at`. Lower sequence numbers that arrive later are accepted if unique and receive an `out_of_order_sequence` flag. ESP32 should still use monotonically increasing sequences and retry safely.

## Latest

`GET /api/v1/outlet/latest?device_id=AQUASENTINEL-01`

Returns the most recently captured sample. `data_status` is `available`, `stale` or `no_data`. No-data response uses null timestamps and an empty measurements object.

## History

`GET /api/v1/outlet/history?device_id=...&from=...&to=...&parameter=tds&limit=500&cursor=...`

- `from` inclusive; `to` exclusive; both timezone-aware.
- Maximum configured range: 31 days by default.
- Ascending order by `(captured_at, id)`.
- `parameter` can be `tds`, `ph`, `turbidity`, `temperature`; omitting it returns all four measurements for each sample.
- `next_cursor` is opaque and can be sent unchanged on the next request.
- Missing values stay null; gaps are not filled.

## Summary

`GET /api/v1/outlet/summary?device_id=...&window=30m&limit=24`

Returns `items` ordered newest first. Only windows closed beyond the configured late-arrival allowance are included. Each item uses fixed UTC boundaries `[hh:00, hh:30)` and `[hh:30, next hh:00)`.

Per-parameter counts:

- `expected_count`: 180 for a 10-second interval; calculated from `SAMPLING_INTERVAL_SECONDS`.
- `received_count`: non-null values received.
- `valid_count`: non-null, `status=valid`, `calibrated=true` values used in statistics.
- `invalid_count`: readings explicitly marked invalid.
- `uncalibrated_count`: readings marked valid but not calibrated.
- `missing_count`: `max(expected_count - received_count, 0)`.
- `received_coverage_percent`: received / expected, capped at 100%.
- `valid_coverage_percent`: eligible / expected, capped at 100%; `coverage_percent` is the same value.

Statistics are null when no eligible values exist. `usable` states whether valid-data coverage reaches the configured data-quality minimum. It does not represent water safety.

## Device status

`GET /api/v1/device/status?device_id=...`

Status is inferred from most recent backend receipt time, not direct Wi-Fi signal strength. The default stale threshold is 120 seconds. Counts cover the last 24 hours.

## Not exposed as working endpoints in this milestone

Historical `/locations` and `/historical-context` await integration with Person 1's existing historical engine. `/filter-health` and `/decision` are deliberately absent until validated. No purifier commands are exposed.
