# AquaSentinel System Architecture

## 1. Purpose

AquaSentinel is a source-aware water-intelligence and RO outlet-monitoring prototype. The current design has a historical source-information path and a live treated-water outlet path. A future evidence-fusion engine will use both paths to generate explainable recommendations.

## 2. Physical and logical measurement points

### Historical source context (inlet-side context)

The current system does not have live inlet sensors. It retrieves previously collected CGWB groundwater or CPCB surface-water records based on a user-selected source and supported location. These records are contextual evidence, not a contemporaneous inlet sample.

### Live outlet monitoring

The ESP32 reads four sensors installed at the treated-water outlet:

- TDS estimate (ppm)
- pH
- Turbidity (NTU only after appropriate calibration)
- Water temperature (°C)

## 3. Runtime data flow

1. Person 3 selects source type and location in the dashboard.
2. Dashboard requests supported locations and the historical profile from Person 1's FastAPI backend.
3. Backend calls the existing historical-context module and returns the structured profile with source provenance, match quality, parameter-specific dates, statistics and quality flags.
4. Person 2's ESP32 acquires outlet sensor readings and submits a telemetry payload over HTTPS to the backend.
5. Backend validates and stores every accepted raw reading. It records both device timestamp and server receipt timestamp.
6. Backend serves the latest readings to the dashboard.
7. At the end of each 30-minute window, backend creates a summary only if the configured data-coverage requirements are met.
8. Dashboard displays live readings separately from the latest completed 30-minute summary.
9. Future filter-performance and decision-engine modules may consume these stored records and historical context.

## 4. Backend hosting and connectivity

Initial host: Person 1's Ubuntu laptop.

- FastAPI binds to a local port, e.g. `127.0.0.1:8000`.
- A secure tunnel (planned: Cloudflare Tunnel) provides remote HTTPS access.
- ESP32 and dashboard can connect from different internet networks; they do not need to share the same Wi-Fi.
- Laptop power, internet, FastAPI and tunnel availability are required. If any is offline, ingestion/API access is interrupted.
- ESP32 should retry and buffer a limited number of readings; it must not assume every POST succeeded.

## 5. Separation of responsibilities

- Historical source context is owned by Person 1 and remains separate from sensor firmware.
- Sensor acquisition and telemetry are owned by Person 2.
- Dashboard display and source/location interaction are owned by Person 3.
- Person 1 owns backend ingestion, validation, storage, summaries and future decision logic.

## 6. Safety and interpretation boundaries

- Historical data is not live inlet data.
- Outlet TDS, pH, turbidity and temperature do not detect all contaminants.
- Normal outlet readings do not establish absence of arsenic, lead, pathogens or other unmeasured hazards.
- Outlet trends can indicate a need to investigate, but without inlet measurements, flow or pressure they cannot uniquely identify a filter or prove membrane degradation.
- No percentage filter-health score or remaining-life estimate is justified by the initial sensor set.
- V1 is monitoring and decision-support preparation, not automatic RO control.
