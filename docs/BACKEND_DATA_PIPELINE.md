# AquaSentinel Backend Data Pipeline

## 1. Acquisition

- Four sensors are installed at the treated-water outlet in the current design: TDS, pH, turbidity and water temperature.
- ESP32 samples at a configurable interval; initial target is 10 seconds.
- Each payload contains device ID, sequence number, capture timestamp, measurement point, sensor values, units, validity status and calibration state.

## 2. Ingestion

For each request:

1. Authenticate the ESP32 device.
2. Validate content type, payload size, schema version and required fields.
3. Validate measurement point, units, finite numeric values and allowed status values.
4. Validate timestamp and sequence number.
5. Record server receipt time independently of device capture time.
6. Detect duplicate `(device_id, sequence)` submissions.
7. Store the accepted raw sample and relevant metadata transactionally.
8. Return an acknowledgement.

A sample with one failed sensor should not force all other sensor measurements to be discarded if the envelope is valid. Store each sensor's status and null value explicitly; exclude invalid/unavailable measurements from relevant statistics.

## 3. Raw storage

Keep raw samples for troubleshooting, charting and later reprocessing. A database record should preserve device ID, sequence, captured_at, received_at, firmware version, measurement point, values, units, per-sensor status and calibration state.

Recommended uniqueness rule: `(device_id, sequence)`. Add time/device indexes for history queries.

## 4. Latest readings

`GET /api/v1/outlet/latest` returns the latest accepted sample or latest usable value per parameter, with both capture and receipt timestamps. The response must make stale/no-data conditions explicit.

## 5. Thirty-minute aggregation

- Fixed windows in UTC: `[hh:00, hh:30)` and `[hh:30, next hh:00)`.
- Initial target sampling interval: 10 seconds; nominal expected count is 180 per sensor per window.
- Calculate expected count from configured interval and actual window duration.
- Calculate received, valid, invalid, uncalibrated and missing counts per parameter.
- Return both received coverage and valid/eligible-data coverage, with a documented denominator.
- Mean, median, minimum, maximum and standard deviation use only eligible measurements. Define eligibility (at minimum: non-null, status `valid`, calibrated `true`) and return counts for excluded records.
- Do not impute or interpolate missing samples in the V1 summary.
- Close windows only after window end plus a configurable late-arrival allowance. Late samples should either trigger an idempotent recomputation or be flagged according to a documented policy.
- Aggregation must be idempotent and support backfilling closed windows after restart.
- Persist one summary per `(device_id, window_start, window_end)`.

## 6. Dashboard polling

- Latest outlet values: poll every 5–10 seconds initially, with backoff on errors.
- Raw history: query only the selected range and page/downsample longer periods.
- 30-minute summary: fetch after the window closes or poll less frequently for a new completed window.
- Device status: derive from most recent received telemetry and a documented stale timeout.

## 7. Filter performance (future)

Use multi-window trends and optional manually recorded maintenance history. A single reading or one 30-minute summary is not sufficient to claim filter degradation. The four outlet sensors cannot identify a failed individual stage or prove membrane fouling. A feedwater TDS measurement would later permit comparison of feed and permeate TDS, but even that is only an operational indicator, not a full contaminant-removal verification.

## 8. Historical context (separate refresh policy)

Historical summaries are retrieved when the user changes the source/location or when the underlying dataset version changes. They are not re-computed every 30 minutes. Historical data remains labelled by source, location, sampling date and parameter-specific freshness.
