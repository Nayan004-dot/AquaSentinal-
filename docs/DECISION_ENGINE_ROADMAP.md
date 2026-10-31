# RO Decision Engine — R&D Roadmap

## Status

R&D in progress. No operating recommendation or automatic RO control should be displayed as functional in Dashboard V1.

## Intended inputs

1. Historical source profile from CGWB/CPCB: source type, selected location, match quality, per-parameter statistics, sample dates, missingness, freshness and quality flags.
2. Outlet sensor profile: TDS, pH, turbidity and temperature with units, calibration state, timestamps, baseline and trend information where available.
3. Filter-performance indicators: persistence of observed outlet trends and manually recorded maintenance/service history.
4. Equipment context: only manufacturer-supported purifier modes, limits and operating constraints once verified.

## Proposed processing stages

1. Validate each input independently.
2. Assess historical source evidence without treating it as current inlet data.
3. Assess outlet readings and their data quality.
4. Assess persistent outlet trends as indirect performance indicators.
5. Evaluate evidence relevance, freshness, completeness and conflicts.
6. Fuse findings using documented, explainable rules.
7. Produce separate source, outlet and filter assessments, plus an overall recommendation with reason codes and limitations.

## Important non-equivalences

- Historical inlet/source records and live outlet readings are not interchangeable.
- Historical chemical concerns cannot be cleared by normal TDS, pH, turbidity or temperature values.
- Outlet deviations do not independently prove filter failure; feedwater changes and sensor drift are alternative explanations.
- No single arbitrary weighted score should hide missing data or weak evidence.

## Initial recommendation categories

- Retain current manufacturer-approved configuration.
- Verify sensor/calibration.
- Investigate outlet-water deviation.
- Review historical source concern and obtain contaminant-specific testing.
- Review purifier/filter maintenance.
- Request manual review because evidence is insufficient.

## Validation before operating changes

Do not recommend pressure, recovery, flow, flushing or mode changes unless there is a documented technical basis, verified purifier compatibility and manufacturer-approved operating limits. V1 is advisory-only. Direct hardware control is out of scope until independently validated.
