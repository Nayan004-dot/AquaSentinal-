# Sensor Anomaly Module
**Goal:** Validate pH, EC, turbidity and temperature readings; compare them with a configurable baseline/reference; return deviations and anomaly indicators.

## Tasks
1. Agree on units and measurement point (`inlet` or `outlet`).
2. Configure baseline values in `config/baseline.json`; avoid hard-coding values throughout the code.
3. Validate missing, non-numeric and implausible readings.
4. Calculate parameter-specific deviations. Use absolute pH differences rather than percentage pH deviations.
5. Document how thresholds were chosen; label unvalidated thresholds as experimental.
6. Test normal, unusual, missing and invalid inputs.

**Output contract:** `../contracts/sensor_output.schema.json`.

The baseline must match the measurement point. An RO outlet baseline is not a valid normal baseline for raw inlet water.
