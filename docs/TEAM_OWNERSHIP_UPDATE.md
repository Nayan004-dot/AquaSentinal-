# AquaSentinel Team Ownership — Backend Handoff Update

The team has decided to transfer implementation of the FastAPI backend from Person 1 to a designated backend developer. The following ownership boundaries should be confirmed before work starts.

| Workstream | Owner | Scope |
|---|---|---|
| Historical context | Person 1 | Existing CGWB/CPCB module, dataset interpretation, location/source querying and stable output interface |
| Backend | Assigned Backend Developer | FastAPI, API routes, authentication, validation, SQLite persistence, raw sensor ingestion, 30-minute summaries, device status, tunnel configuration and backend tests |
| ESP32 and sensors | Person 2 | Four outlet sensors, calibration, firmware, timestamps, HTTPS POST telemetry, retries/buffering and hardware test records |
| Dashboard | Person 3 | Source/location selectors, historical display, live outlet cards, graphs, summary display and R&D placeholders |
| Future decision engine | Person 1 | Historical/outlet evidence assessors, evidence quality, fusion rules and explainable recommendations; integrates through backend interfaces |

## Interface ownership

- Backend Developer publishes and maintains backend request/response contracts and API versioning.
- Person 2 makes firmware payloads conform to the sensor-ingestion contract.
- Person 3 consumes the published GET response schemas and does not calculate server-side summaries in the browser.
- Person 1 maintains the historical module and later provides the adapter/interface needed to expose it through the backend. Person 1 also owns future decision logic.

## Team assignment note

A three-person team now has four workstreams because historical context and decision-engine work stay with Person 1 while backend implementation is transferred. The team must explicitly identify which teammate is the Backend Developer and adjust that teammate's previous workload (sensor or frontend) if necessary. Do not assume the new backend role is an additional unowned fourth person.

## Shared working rules

1. Use separate feature branches.
2. Agree to JSON contracts before end-to-end integration.
3. Use mock payloads for parallel frontend/firmware work.
4. Keep all secrets outside Git.
5. Breaking API changes must be announced to ESP32 and frontend owners.
6. Backend README/run instructions and tests must be maintained by the Backend Developer.
