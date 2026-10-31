# AquaSentinel Sensor Data Pipeline

## 1. Acquisition and transport

ESP32 samples the four outlet sensors at a configurable interval. Initial engineering target: one sample every 10 seconds. Person 2's firmware submits a JSON payload over HTTPS to Person 1's FastAPI backend.

## 2. Backend ingestion

For each received payload, backend:
1. Authenticates the device.
2. Validates schema, units, timestamp and sequence number.
3. Records server `received_at` in addition to device `timestamp`.
4. Preserves nulls and explicit validity/calibration statuses.
5. Detects duplicate sequence numbers and gaps.
6. Stores the raw accepted sample.
7. Returns an acknowledgement to ESP32.

## 3. Live dashboard path

Dashboard polls latest readings approximately every 5–10 seconds initially. It displays measurement time, server receipt time and freshness so a stale reading is not mistaken for a live measurement.

## 4. 30-minute aggregation

Backend groups data into fixed half-hour windows. At window close, calculate for each sensor parameter:
- expected count
- received count
- valid count
- invalid/missing count
- coverage percentage
- mean, median, minimum, maximum and standard deviation when sufficient valid observations exist
- relevant calibration and quality flags

For a 10-second interval, the nominal expected count is 180 samples per parameter per 30-minute window. Actual coverage can be lower. Configure a minimum coverage rule before a summary is marked complete; do not silently fill missing samples or publish incomplete statistics as a full-window summary.

Keep raw readings after aggregation. They are needed for audit, troubleshooting and alternate trend windows.

## 5. Longer-term monitoring

Daily and 7-day trend calculations may use raw records or 30-minute summaries. Filter-performance assessment is not simply a flag on one high or low reading. It should consider persistence, data coverage, sensor calibration and historical trends. In the current outlet-only design, such findings are indirect indicators and cannot uniquely establish filter failure.

## 6. Historical context update cadence

Fetch historical context when the dashboard source/location changes or when the underlying dataset version is updated. The 30-minute sensor aggregation cadence does not apply to CGWB/CPCB historical queries.
