# Backend Developer Handoff — AquaSentinel V1

## Assignment

**Owner:** Backend developer assigned by the team.

**Deployment host:** Person 1's Ubuntu laptop.

**Primary responsibility:** Implement and document the FastAPI service that receives ESP32 outlet telemetry, stores it, produces 30-minute summaries, and provides read APIs for Person 3's dashboard.

Person 1 retains ownership of the existing historical-context module and the future RO decision engine. The backend developer must coordinate with Person 1 on the historical-context integration boundary, but must not rewrite that module.

## What to build

### Milestone 1 — API skeleton

- Create a Python backend package using FastAPI and Pydantic.
- Add configuration through environment variables.
- Add `GET /api/v1/health`.
- Add `/docs` Swagger UI for development.
- Add tests and a documented local run command.

Acceptance: service starts on Person 1's laptop and health endpoint returns service status and API version without exposing secrets.

### Milestone 2 — Sensor ingestion

Implement `POST /api/v1/sensors/outlet`.

- Require device-specific authentication (for example, `X-Device-Token`).
- Validate the agreed JSON schema and units.
- Validate ISO 8601 timestamp, device ID, non-negative sequence number and `measurement_point = outlet`.
- Accept explicit missing values as `null` only with an appropriate sensor status.
- Reject NaN/Infinity, malformed JSON, unsupported units and oversized payloads.
- Record server `received_at` independently.
- Deduplicate using `(device_id, sequence)`.
- Return a clear acknowledgement and HTTP status.

Acceptance: a valid sample can be sent with curl/Postman and stored exactly once. Invalid and duplicate payloads are handled predictably.

### Milestone 3 — SQLite persistence

Persist raw sample envelopes and per-sensor measurements, or use an equivalent normalized schema. Preserve:

- device ID
- sequence number
- capture timestamp
- backend receipt timestamp
- firmware version (if sent)
- measurement point
- each sensor value and unit
- sensor validity status
- calibration status
- ingestion/quality flags

Use a unique constraint on `(device_id, sequence)`. Add indexes for device/time queries. Keep raw data after summarization.

Acceptance: data survives application restart; duplicate sequence numbers cannot create a second record.

### Milestone 4 — Dashboard read APIs

Implement:

- `GET /api/v1/outlet/latest?device_id=...`
- `GET /api/v1/outlet/history?device_id=...&from=...&to=...`
- `GET /api/v1/outlet/summary?device_id=...&window=30m`
- `GET /api/v1/device/status?device_id=...`

History endpoint must validate time ranges, limit result size and support pagination or documented downsampling. No-data responses must use explicit empty/null fields, not zero.

Acceptance: Person 3 can build the outlet dashboard using only these GET endpoints and the documented JSON response shapes.

### Milestone 5 — 30-minute summaries

- Use fixed UTC half-hour windows: `[hh:00, hh:30)` and `[hh:30, next hh:00)`.
- Initial sensor transmission target is every 10 seconds; nominal expected sample count is 180 per sensor per window.
- Aggregate only eligible readings for statistics; report invalid, uncalibrated and missing counts separately.
- Return mean, median, min, max and standard deviation when sufficient data exists.
- Return expected/received/valid/invalid/uncalibrated/missing counts and coverage.
- Require a configurable minimum coverage before marking a summary usable.
- Do not publish a completed summary before its window closes.
- Make aggregation idempotent and backfill closed windows after restart.

Acceptance: a test fixture representing a full and a partial window produces correct statistics and coverage; rerunning aggregation does not duplicate or alter the result unexpectedly.

### Milestone 6 — Remote connectivity

- Run FastAPI locally on the laptop, preferably bound to `127.0.0.1` when accessed through a local tunnel process.
- Configure a named/temporary secure tunnel that forwards the public HTTPS hostname to the local FastAPI port.
- Give Person 2 the public HTTPS ingestion URL and device token through a private channel, not GitHub.
- Give Person 3 the public API base URL and any dashboard-specific access configuration.
- Confirm requests work from a different network (for example, ESP32 on a phone hotspot while laptop is elsewhere).

Acceptance: ESP32 and dashboard can reach the API without sharing the laptop's Wi-Fi. The laptop, API and tunnel must remain online.

## Ownership boundaries

- Backend developer owns FastAPI routes, validation, persistence, aggregation, device status, configuration, API docs and tests.
- Person 2 owns sensor electronics, calibration, ESP32 firmware, NTP/timekeeping, HTTPS client, retry and buffering behavior.
- Person 3 owns frontend implementation, user interaction, charts, display states and API consumption.
- Person 1 owns the existing historical-context logic and future evidence-fusion/decision-engine logic. Person 1 provides a stable historical-context callable/JSON contract for later backend integration.

Because the three-person allocation is being adjusted, the team must explicitly confirm which teammate is the Backend Developer and whether any previous sensor/frontend duties are being reassigned. Avoid assigning two owners to the same files or leaving an unowned integration task.

## Do not implement in this milestone

- Do not implement the RO decision engine.
- Do not invent filter-health percentages, filter-life predictions or fault classifications.
- Do not change Atomberg purifier settings or send control commands.
- Do not read raw historical CSV files from the browser.
- Do not expose SQLite, datasets, debug endpoints or secrets through the tunnel.
- Do not commit API tokens, Wi-Fi passwords or `.env` files.

## Branch and pull request

Suggested branch: `feature/backend-api`.

Before merging, run the backend test suite, verify the API examples against actual responses, and update `docs/BACKEND_API_CONTRACTS.md` if a contract change is necessary. Announce breaking schema changes to Person 2 and Person 3 before merging.
