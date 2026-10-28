# AquaSentinel
Source-aware water-quality intelligence and Edge AI for RO operating recommendations.

## Overview
AquaSentinel combines live sensor measurements (pH, EC, turbidity, temperature) with historical water-quality context selected by source and location. The sensor and historical modules are developed independently first; integration and scoring follow later.

## Repository layout
- `sensor-anomaly/`: configurable baselines, validation, deviations and anomaly flags
- `historical-context/`: CGWB groundwater and CPCB surface-water data processing
- `contracts/`: shared output schemas
- `integration/`: future combined scoring and inference
- `docs/`: architecture and integration plan
- `tests/`: future cross-module tests

## Data sources
- CGWB: groundwater-quality datasets from India's National Water Data Portal
- CPCB: surface-water-quality datasets from India's National Water Data Portal

Preserve source type, location/station, sampling date, units and provenance. Do not treat groundwater and surface-water records as interchangeable.

## Safety and interpretation
- pH, EC, turbidity and temperature do not directly detect all contaminants, including arsenic, lead and pathogens.
- Historical records describe sampled conditions at a place and time; they do not prove current inlet quality.
- Missing measurements are unavailable, not zero risk.
- A risk score does not directly determine RO pressure, recovery rate or flushing settings. Recommendations require validated rules and operating data.
- The initial prototype is decision support, not automatic physical RO control.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
```
