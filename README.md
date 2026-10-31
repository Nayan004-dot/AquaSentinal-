# AquaSentinel

**Source-aware water intelligence and outlet monitoring for RO systems.**

AquaSentinel combines historical source-water context with live measurements from the treated-water outlet. Its goal is to provide traceable water-quality monitoring, identify possible filtration-performance changes, and — in a later phase — generate explainable RO operating recommendations.

> **Current scope:** The historical-context module is implemented. Dashboard V1 is being built around two functional sections: Historical Source Intelligence and Outlet Water Monitoring. Filter Performance & Maintenance Monitoring and the RO Decision Engine are clearly marked as R&D / upcoming until their logic is implemented and validated.

## System architecture

```text
                         PERSON 3 — WEB DASHBOARD
            ┌──────────────────────────────────────────────┐
            │ Historical Source Intelligence               │
            │ Outlet Water Monitoring                       │
            │ Filter Performance (R&D in progress)          │
            │ RO Decision Engine (R&D in progress)          │
            └──────────────────────┬───────────────────────┘
                                   │ HTTPS / REST API
                                   ▼
             PERSON 1 — UBUNTU LAPTOP / CENTRAL BACKEND
            ┌──────────────────────────────────────────────┐
            │ FastAPI backend                              │
            │ Historical-context module (CGWB / CPCB)      │
            │ Sensor ingestion and validation              │
            │ Raw reading storage and 30-minute summaries  │
            │ Filter trend assessment (planned)             │
            │ Evidence-fusion decision engine (planned)    │
            └──────────────────────▲───────────────────────┘
                                   │ HTTPS POST
                                   │ Internet / secure tunnel
                                   │
                         PERSON 2 — ESP32 SENSOR NODE
            ┌──────────────────────────────────────────────┐
            │ Outlet TDS                                    │
            │ Outlet pH                                     │
            │ Outlet turbidity                              │
            │ Outlet water temperature (DS18B20)            │
            └──────────────────────────────────────────────┘
```

The laptop is the processing host in the initial deployment. A secure tunnel (planned: Cloudflare Tunnel) provides internet access to the laptop-hosted API, so the ESP32 and dashboard do not need to be on the same Wi-Fi network. The laptop, FastAPI service and tunnel must remain online for remote access. A tunnel provides connectivity; it does not move backend computation or datasets into the cloud.

## Dashboard V1 scope

### Functional sections

1. **Historical Source Intelligence**
   - Select source type: `groundwater` or `surface_water`.
   - Select a supported location from the corresponding dataset.
   - Display the CGWB/CPCB source, location match, observation count, sample-date range, per-parameter statistics, latest valid measurement date, freshness, missing values and quality flags.
   - Historical summaries are retrieved when the source/location is selected or when the underlying dataset is updated. They are not treated as live inlet readings and do not need a 30-minute refresh.

2. **Outlet Water Monitoring**
   - Receive readings from the ESP32 sensor node.
   - Display the latest valid TDS, pH, turbidity and water-temperature measurements, timestamps, sensor validity and calibration status.
   - Display time-series history and the latest completed 30-minute analytical summary.
   - Keep raw readings; do not discard them after summarization.

### R&D sections (not functional in V1)

3. **Filter Performance & Maintenance Monitoring — R&D in Progress**
   - Planned indirect assessment from persistent outlet trends, sensor quality, and manually recorded filter-service history.
   - The four outlet sensors cannot directly identify a failed filter stage, confirm membrane fouling, or produce a defensible filter-health percentage.

4. **RO Decision Engine — R&D in Progress**
   - Planned evidence fusion of historical source context, outlet measurements and filter-performance indicators.
   - Will return an explainable assessment and advisory recommendation only after rules and limits are validated.
   - No direct RO hardware control is implemented in V1.

## Sensor and data pipeline

- **Measurement point:** all four ESP32 sensors are located at the treated-water outlet in the current design.
- **Parameters:** TDS (ppm), pH, turbidity (NTU only when appropriately calibrated), and water temperature (°C).
- **Initial acquisition/transmission interval:** 10 seconds, configurable after bench testing.
- **Backend ingestion:** every received sample is validated and stored as a raw record.
- **Dashboard latest-value refresh:** approximately every 5–10 seconds, configurable.
- **Analytical aggregation:** summarize each completed 30-minute window. Include mean, median, min, max, standard deviation, valid/invalid counts and coverage. Do not show a completed summary until the window has closed and meets the configured minimum-data requirement.
- **Longer trends:** use stored raw data and/or completed summaries for 24-hour and 7-day analysis. Filter-performance assessment remains R&D until its criteria are validated.

## Team ownership

| Owner | Primary responsibility | Main deliverables |
|---|---|---|
| **Person 1** | Historical context, central backend and future decision engine | Existing CGWB/CPCB module; FastAPI; APIs; validation and storage; 30-minute summaries; later evidence-fusion decision engine |
| **Person 2** | ESP32 and sensor acquisition | Four outlet sensors; calibration; firmware; Wi-Fi/HTTPS telemetry; retry and reconnection behavior; hardware test records |
| **Person 3** | Dashboard and user interaction | Historical source/location selection; historical display; outlet cards and graphs; 30-minute summary display; R&D placeholders; API integration |

All three owners must use the shared contracts in [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md). Person 1 owns backend response formats; Person 2 owns ESP32 telemetry compatibility; Person 3 consumes the documented API and displays backend responses. The dashboard must not read CSV files or independently calculate historical summaries.

## API overview

The proposed V1 endpoints are documented in [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md):

- `GET /api/v1/locations?source_type=groundwater`
- `GET /api/v1/historical-context?source_type=groundwater&location_id=...`
- `POST /api/v1/sensors/outlet`
- `GET /api/v1/outlet/latest`
- `GET /api/v1/outlet/history`
- `GET /api/v1/outlet/summary`
- `GET /api/v1/device/status`

Filter assessment and decision endpoints are reserved for later development and should not be represented as working V1 features.

## Data sources and interpretation

- **CGWB:** groundwater-quality records.
- **CPCB:** surface-water-quality records.

Keep groundwater and surface-water records separate. Preserve source, station/location, sampling date, original parameter name, units, provenance and quality flags. Prefer station-level matching; label weaker location matches explicitly.

Historical observations describe sampled conditions at a place and time. They are not live inlet measurements. The four outlet sensors measure only the parameters listed above and do not directly detect arsenic, lead, pathogens or every other contaminant. Missing measurements mean unavailable, not zero. A normal TDS/pH/turbidity/temperature reading cannot establish overall drinking-water safety.

## Security and deployment

- FastAPI runs on Person 1's Ubuntu laptop initially.
- Use HTTPS through a secure tunnel for access outside the local network.
- Require device authentication for sensor POST requests.
- Validate payload types, units, timestamps, sequence numbers and device IDs.
- Keep API tokens and Wi-Fi credentials out of Git and frontend code.
- Restrict CORS to the intended dashboard origin.
- Do not expose raw CSVs, SQLite files, debug routes or unauthenticated admin endpoints publicly.
- ESP32 should buffer/retry a limited number of readings after network failures; the backend must detect duplicate sequence numbers.

## Repository structure (target)

```text
historical-context/       Existing CGWB/CPCB historical module
sensor-module/            ESP32 firmware and sensor calibration
backend/                  FastAPI app, storage and API routes
filter-monitor/           Future indirect trend/maintenance assessment
decision-engine/           Future historical/outlet evidence fusion
dashboard/                Person 3 frontend
contracts/                Shared JSON schemas and examples
docs/                     Architecture, APIs, ownership and development plan
```

The target structure can be introduced incrementally. Do not move or rewrite the working historical-context implementation merely to match this sketch.

## Local development (backend)

Once the backend application exists, a typical development run will look like:

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The exact import path may differ depending on the implemented package layout. For remote access, run a configured secure tunnel that forwards to the local FastAPI port. Use a stable named tunnel for a persistent deployment; temporary tunnel URLs are for testing only.

## Current implementation status

| Component | Status |
|---|---|
| Historical-context processing and CLI | Implemented locally; preserve and test existing code |
| Dashboard V1 historical section | Frontend development |
| ESP32 outlet sensor acquisition | Planned / in development |
| Backend sensor ingestion | Planned |
| Raw sensor storage and 30-minute summaries | Planned |
| Dashboard V1 outlet section | Frontend development; awaiting real telemetry |
| Filter performance & maintenance assessment | R&D in progress |
| RO decision engine | R&D in progress |
| Atomberg purifier integration/control | Not implemented; manufacturer interface and limits must be verified |

Do not mark a component complete until its code, tests and end-to-end behavior have been verified.
