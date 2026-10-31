# Dashboard V1 Specification

## Active sections

V1 has exactly two functional sections. Two future sections may appear as clearly labelled cards, but must not display fabricated results.

## 1. Historical Source Intelligence

### Controls
- Source selector: Groundwater / Surface Water.
- Searchable location selector populated through `GET /api/v1/locations`.
- Fetch/refresh action.
- Loading, no-match, ambiguous-match, error and stale-data states.

### Overview cards
- Dataset agency/name.
- Requested location and matched location.
- Match level and matched field.
- Observation count.
- Earliest and latest station sample dates.

### Parameter table
Columns:
- Parameter and original source name.
- Unit.
- Mean, median, minimum, maximum and standard deviation.
- Valid count and missing count.
- Latest valid measurement date.
- Measurement age and freshness/staleness.
- Quality flags.

Dates/freshness must be per parameter. Do not substitute the latest station date for the latest measurement date of every parameter. Null values must render as `—` or `Not available`, never zero. Clearly label the data as historical context, not live inlet monitoring.

## 2. Live Outlet Water Monitoring

Four sensor cards:
- TDS (ppm)
- pH
- Turbidity (NTU only when calibrated accordingly)
- Water temperature (°C)

Each card shows latest value, unit, measurement timestamp, device receipt freshness, validity and calibration state. Show baseline/deviation only if backend provides a defined baseline and calculation.

Charts:
- TDS over time
- pH over time
- Turbidity over time
- Temperature over time

Suggested filters: 1 hour, 6 hours, 24 hours and 7 days. Display only available data and handle gaps visibly.

### 30-minute analytical summary

Show the latest completed 30-minute window separately from live cards. Include window start/end, sample counts, data coverage and mean/median/min/max/standard deviation per valid sensor parameter. Explain incomplete windows; do not present them as complete.

## R&D cards (not functional)

### Filter Performance & Maintenance Monitoring
Label: `R&D IN PROGRESS`.
Description: "Planned indirect assessment of possible filtration-performance changes using persistent outlet measurement trends and maintenance records."
Do not show a filter-health percentage, remaining lifetime, failed stage or confirmed membrane fouling.

### RO Decision Engine
Label: `R&D IN PROGRESS`.
Description: "Planned evidence fusion of historical source context, live outlet measurements and filter-performance indicators to generate explainable RO operating recommendations."
Do not show a decision or recommended RO mode in V1.

## Overview page

Display:
- Selected source and location.
- Historical data status and sample date range.
- Latest outlet sensor readings.
- Latest completed 30-minute summary timestamp/status.
- ESP32 connectivity and last received time.
- Two R&D cards with progress labels.

## UX requirements

- Responsive desktop-first dashboard.
- Clear visual distinction between historical records and live outlet measurements.
- Visible timestamps and units.
- Distinct states for loading, stale, unavailable, disconnected, invalid and error.
- Use actual API responses; mock data must be labelled as demonstration data.
- Frontend only renders backend results; it does not query CSVs or calculate historical statistics.
