# Team Responsibilities and Handoffs

The team has three owners. Each person owns a separate subsystem and integrates through the shared API contracts.

## Person 1 — Historical Context, Backend and Decision Engine (team lead)

### V1 responsibilities
- Preserve and maintain the existing CGWB/CPCB historical-context module and CLI.
- Expose supported source/location choices through the backend.
- Build the FastAPI application and historical-context endpoints.
- Build the ESP32 sensor-ingestion endpoint.
- Validate telemetry: device ID, timestamp, sequence, units, nulls, values and sensor validity.
- Store accepted raw readings and server receipt timestamps (SQLite is suitable for the prototype).
- Generate 30-minute sensor summaries and expose latest/history/summary endpoints.
- Configure secure remote access to the laptop-hosted API (planned Cloudflare Tunnel).
- Document authentication, CORS, environment variables and service startup.

### Later responsibilities
- Implement indirect filter-performance analysis from sensor trends and service records.
- Implement historical and outlet assessors, evidence-quality checks and the fusion/decision engine.
- Keep recommendations advisory until thresholds and purifier operating limits are validated.

### Deliverables
- Running FastAPI backend.
- Historical data endpoint.
- Sensor ingestion and data storage.
- 30-minute summary endpoint.
- API documentation and example responses.

## Person 2 — ESP32 and Sensor Acquisition

### Responsibilities
- Integrate outlet TDS, pH, turbidity and waterproof DS18B20 temperature sensors.
- Confirm each module's supply voltage and analog output range. Protect ESP32 inputs; ESP32 GPIO is not 5 V tolerant.
- Establish wiring and document GPIO assignments.
- Calibrate pH, TDS and turbidity with suitable reference/calibration procedures; only report turbidity in NTU when calibration supports it.
- Acquire readings at a configurable interval (initial target: 10 seconds; confirm after sensor stability and network testing).
- Include device ID, monotonically increasing sequence number, device timestamp, values, units and per-sensor validity/calibration state.
- Connect to Wi-Fi and send HTTPS POST requests to Person 1's public API URL.
- Parse HTTP responses, retry safely, reconnect after Wi-Fi failure and buffer a limited number of unsent samples if practical.
- Never report missing/failed readings as zero.
- Test with a mock receiver first, then the real backend.

### Deliverables
- ESP32 firmware.
- Wiring and pinout document.
- Calibration/test log.
- Example telemetry JSON.
- End-to-end successful POST test and network-failure behavior.

## Person 3 — Dashboard and Frontend

### Functional V1 sections

#### A. Historical Source Intelligence
- Provide source selector: `groundwater` / `surface_water`.
- Request the supported locations list from Person 1's API; location options must depend on source type.
- Send the selected source and location to the backend.
- Display agency/dataset, requested and matched location, match quality, observation count, sampling date range and latest station date.
- Display per-parameter unit, mean, median, min, max, valid count, missing count, latest valid measurement date, age/freshness and quality warnings.
- Preserve separate parameter dates. Do not show missing values as zero.
- Clearly label this section as historical source context, not live inlet monitoring.

#### B. Outlet Water Monitoring
- Fetch latest sensor readings from the backend.
- Display TDS, pH, turbidity and temperature cards with units, timestamps, validity and calibration state.
- Display baseline and deviation only when backend provides them.
- Display time-series graphs from backend history endpoints.
- Display the most recent completed 30-minute summary, including window start/end, mean, median, min, max, standard deviation, valid/invalid count and coverage.
- Clearly distinguish latest live readings from completed 30-minute summaries.
- Handle no data, stale data, disconnected device and API failure states.

### R&D placeholders (not functional V1 sections)
- Filter Performance & Maintenance Monitoring — show “R&D in Progress”.
- RO Decision Engine — show “R&D in Progress”.
- Do not fabricate filter-health percentages, decisions or RO mode recommendations.

### Deliverables
- Responsive dashboard.
- Source/location selection.
- Historical profile visualizations.
- Outlet sensor cards and graphs.
- 30-minute summary display.
- R&D placeholders.
- API integration using `VITE_API_BASE_URL`.

## Integration rules for everyone

1. Agree to the request/response contracts in `API_CONTRACTS.md` before integration.
2. Use mock JSON matching those contracts during parallel development.
3. Person 1 owns backend field names and API versioning.
4. Person 2 owns compatibility of ESP32 telemetry with the sensor-ingestion contract.
5. Person 3 consumes the API; the browser must not parse raw CGWB/CPCB CSV files or implement historical analysis.
6. Do not put credentials, Wi-Fi passwords or device tokens in Git.
7. Use separate feature branches and merge through pull requests.
8. Label unfinished features as R&D, not implemented.
