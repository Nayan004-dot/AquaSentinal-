# Historical Water-Quality Context Module
**Goal:** Given source type and location, return a source-aware historical profile from relevant CGWB groundwater or CPCB surface-water records.

## Tasks
1. Download and document official datasets and download dates.
2. Inspect actual CSV columns; don't assume resources share schemas.
3. Standardize parameter names, units, dates and location fields while preserving original values.
4. Match by monitoring station when possible; use district fallback only when clearly labelled.
5. Summarize parameters: count, mean/median, min/max, variability, latest sample date, and exceedance statistics only when a suitable standard and unit are available.
6. Preserve source, station, location, dates, provenance and quality flags.
7. Test missing parameters, unmatched locations, sparse records and duplicates.

**Output contract:** `../contracts/historical_profile.schema.json`.

Do not mix groundwater and surface-water records. Missing contaminant measurements are unavailable, not zero risk. Historical measurements are not current live readings.
