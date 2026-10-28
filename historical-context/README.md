# Historical water quality context

This module builds a descriptive historical profile from a supplied CGWB groundwater or CPCB surface-water CSV. It does not produce risk scores, infer safety, apply drinking-water limits, or represent current conditions.

## Public API

`src.historical_context.get_historical_profile(csv_path, source_type, location, *, as_of=None)` returns a JSON-serializable dictionary. `source_type` is `groundwater` or `surface_water`; `location` is a non-empty string. The optional `as_of` date (ISO format recommended) makes record-age calculations reproducible; otherwise the current UTC date is used.

Matching checks case-insensitive exact text in this order: station, village, block, tehsil, district, river. The returned `match_level` and `matched_column` identify the first field level that matched. Exact text matching does not establish geographic proximity. If one exact station name refers to multiple distinct location identities, the result is `match_level: "ambiguous"`, has no aggregated profile (`sample_count: 0`, empty `parameters`), and lists the station candidates and their observation counts. Repeated observations for one station identity remain valid and are summarized together. District matches carry a `district_level_match` flag, and unmatched requests carry `unmatched_location`.

The stable output keys are `source_type`, `dataset_agency`, `requested_location`, `match_level`, `matched_column`, `sample_count`, `candidate_sample_count`, `earliest_sample_date`, `latest_sample_date`, `record_age_days`, `date_column`, `date_missing_count`, `parameters`, `ambiguous_candidates`, `zero_value_diagnostics`, `measurement_columns_present`, `measurement_columns_missing`, and `data_quality_flags`, plus `geographic_proximity_established` and `historical_data_only`. Unmatched results have zero sample counts, null date values/count, and empty parameters. Ambiguous results also have zero selected samples and empty parameters; `candidate_sample_count` describes the rows requiring disambiguation. Matched results count the selected observations, including legitimate repeated observations at one station.

Measurement selection uses explicit CGWB groundwater and CPCB surface-water column allowlists. Administrative identifiers, coordinates, and unrecognized columns are never summarized. Parameter names and units are retained from the input schema; a separate unit is `null` when the schema does not provide one (including the pH field). Numeric statistics are provided for numeric fields; CPCB `Colour` and `Odour` are represented by category counts. Missing or unparsable numeric measurements are counted and never converted to zero. Missing expected schema columns are listed and flagged. Dates from the source's day-first formats and unambiguous ISO formats are normalized to UTC; naive dates are interpreted as UTC. `as_of` strings must be ISO-8601 to avoid ambiguous day/month parsing, use the same UTC convention, and invalid values raise `ValueError`. A record older than 365 days is flagged as stale, a descriptive cutoff rather than a claim about water quality; samples after `as_of` receive `sample_date_after_reference` and may have a negative age.

Numeric zero values are preserved in counts and statistics. Trace-metal zeros are listed in `zero_value_diagnostics` and add `trace_metal_zero_values_unverified` to the quality flags. This is a caution, not a finding that the source data is wrong: the analytical meaning of a recorded zero has not been verified, and it does not establish contaminant absence or a below-detection-limit result. A blank is counted as missing separately from a numeric zero. No detection limits are inferred.

## Example

Run this snippet from the `historical-context/` directory:

```python
from src.historical_context import get_historical_profile

profile = get_historical_profile(
    "datasets/raw/gwq_chemical_parameter_manual_cgwb_up_1961_2025.csv",
    "groundwater",
    "Aandwa",
)
print(profile["match_level"], profile["latest_sample_date"])
```

## Command-line query

Run commands from the repository root. The CLI selects the local CGWB or CPCB CSV based on `--source`; these paths are resolved relative to `query.py`, so the current working directory does not affect default dataset lookup.

```bash
.venv/bin/python historical-context/query.py --source groundwater --location Aandwa
.venv/bin/python historical-context/query.py --source surface_water --location "AGRA CANAL MADANPUR KHADAR DELHI"
```

Optional flags provide a reproducible `YYYY-MM-DD` reference date, a custom CSV, or JSON output:

```bash
.venv/bin/python historical-context/query.py --source groundwater --location Aandwa --as-of 2024-01-31
.venv/bin/python historical-context/query.py --source groundwater --location Aandwa --csv /path/to/custom.csv
.venv/bin/python historical-context/query.py --source surface_water --location "AGRA CANAL MADANPUR KHADAR DELHI" --json
```

Readable output includes source and match details, date range and age, measurement counts and summaries, quality flags, and limitations. Missing values display as `N/A`. JSON mode prints a wrapper with the resolved dataset path and the complete profile. Neither format draws safety conclusions; historical observations do not represent current conditions, and exact text matching does not establish proximity.

From the repository root, run the tests with:

```bash
.venv/bin/python -m pytest -q historical-context/tests
```

Raw CSVs under `datasets/raw/` and the project `.venv/` are ignored by Git.
