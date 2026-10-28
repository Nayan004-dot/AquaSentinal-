import json

import pandas as pd
import pytest

from src.historical_context import MEASUREMENT_COLUMNS, get_historical_profile


@pytest.fixture
def groundwater(tmp_path):
    path = tmp_path / "groundwater.csv"
    pd.DataFrame(
        {
            "SlNo": [1, 2, 3], "Station": ["A Station", "B Station", "C Station"],
            "Agency": ["CGWB"] * 3, "State LGD Code": [9] * 3,
            "State": ["Uttar Pradesh"] * 3, "District LGD Code": [10, 10, 20],
            "District": ["Alpha", "Alpha", "Beta"], "Tehsil": ["North", "North", "South"],
            "Block": ["Block One"] * 3, "Village": ["Village One", "Village Two", "Village Three"],
            "River": ["Nile"] * 3, "Latitude": [12.1, 12.2, 13.0], "Longitude": [77.1, 77.2, 78.0],
            "Data Acquisition Time": ["25-05-2004 00:00", "2024-02-03", "bad-date"],
            "Potential of Hydrogen (pH)": [8.1, None, 7.0],
            "Nitrate N (mgN/L)": [None, None, 2.5], "Unexpected Metadata": [44, 55, 66],
        }
    ).to_csv(path, index=False)
    return path


@pytest.fixture
def surface_water(tmp_path):
    path = tmp_path / "surface.csv"
    pd.DataFrame(
        {
            "SlNo": [1, 2], "Station": ["River Station"] * 2,
            "District": ["Alpha"] * 2, "Latitude": [20.0] * 2, "Longitude": [80.0] * 2,
            "Data Acquisition Time": ["06-01-2021 08:30", "07-01-2021 08:30"],
            "Electric Conductivity (μS/cm)": [1015, None], "Colour": ["Clear", "Pale yellow"],
            "Odour": ["Odourless", "Odourless"], "Turbidity (NTU)": [None, None],
            "Temperature (ºC)": [None, None], "Total Solids (mg/L)": [None, None],
            "Unexpected Metadata": [99, 98],
        }
    ).to_csv(path, index=False)
    return path


def test_station_match_precedes_district_and_uses_cgwb_allowlist(groundwater):
    result = get_historical_profile(groundwater, "groundwater", "a station", as_of="2024-01-01")
    assert result["match_level"] == "station"
    assert result["sample_count"] == 1
    assert set(result["parameters"]) == {"Potential of Hydrogen (pH)", "Nitrate N (mgN/L)"}
    assert "Unexpected Metadata" not in result["parameters"]
    assert result["parameters"]["Potential of Hydrogen (pH)"]["unit"] is None
    assert json.loads(json.dumps(result))["historical_data_only"] is True


def test_district_match_and_missing_measurements_are_not_zero(groundwater):
    result = get_historical_profile(groundwater, "groundwater", "Alpha", as_of="2024-02-04")
    nitrate = result["parameters"]["Nitrate N (mgN/L)"]
    assert result["match_level"] == "district"
    assert "district_level_match" in result["data_quality_flags"]
    assert nitrate["measurement_count"] == 0 and nitrate["missing_count"] == 2
    assert nitrate["mean"] is None


def test_unmatched_location_and_invalid_source(groundwater):
    result = get_historical_profile(groundwater, "surface_water", "Nowhere")
    assert result["match_level"] == "unmatched"
    assert result["sample_count"] == 0 and result["parameters"] == {}
    assert "unmatched_location" in result["data_quality_flags"]
    with pytest.raises(ValueError, match="source_type"):
        get_historical_profile(groundwater, "river", "Alpha")


def test_date_parsing_missing_dates_and_timezone_normalization(groundwater, tmp_path):
    result = get_historical_profile(groundwater, "groundwater", "A Station", as_of="2024-06-01")
    assert result["latest_sample_date"] == "2004-05-25"
    assert result["record_age_days"] == 7312
    invalid = get_historical_profile(groundwater, "groundwater", "C Station", as_of="2024-06-01")
    assert invalid["latest_sample_date"] is None and invalid["date_missing_count"] == 1
    path = tmp_path / "tz.csv"
    pd.DataFrame({"Station": ["TZ"], "Data Acquisition Time": ["2024-02-03T23:30:00-05:00"],
                  "Potential of Hydrogen (pH)": [7.1]}).to_csv(path, index=False)
    tz = get_historical_profile(path, "groundwater", "TZ", as_of="2024-02-05T00:00:00+00:00")
    assert tz["latest_sample_date"] == "2024-02-04" and tz["record_age_days"] == 1
    future = get_historical_profile(path, "groundwater", "TZ", as_of="2024-02-03T00:00:00+00:00")
    assert future["record_age_days"] == -1
    assert "sample_date_after_reference" in future["data_quality_flags"]


def test_invalid_as_of_is_rejected(groundwater):
    with pytest.raises(ValueError, match="Invalid as_of"):
        get_historical_profile(groundwater, "groundwater", "missing", as_of="not-a-date")
    with pytest.raises(ValueError, match="Invalid as_of"):
        get_historical_profile(groundwater, "groundwater", "missing", as_of="01-02-2024")


def test_empty_dataset_and_malformed_or_missing_columns(tmp_path):
    empty = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Station", "Data Acquisition Time"]).to_csv(empty, index=False)
    result = get_historical_profile(empty, "groundwater", "Nobody")
    assert result["sample_count"] == 0 and result["latest_sample_date"] is None
    assert "empty_dataset" in result["data_quality_flags"]
    no_header = tmp_path / "no_header.csv"
    no_header.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="no CSV header"):
        get_historical_profile(no_header, "groundwater", "Nobody")
    malformed = tmp_path / "malformed.csv"
    pd.DataFrame({"SlNo": [1], "pH": [7.2]}).to_csv(malformed, index=False)
    missing = get_historical_profile(malformed, "groundwater", "Nobody")
    assert "missing_location_columns" in missing["data_quality_flags"]
    assert "missing_date_column" in missing["data_quality_flags"]
    assert "missing_measurement_columns" in missing["data_quality_flags"]


def test_duplicate_station_name_is_ambiguous_but_repeat_observations_are_not(tmp_path):
    path = tmp_path / "duplicates.csv"
    pd.DataFrame({"Station": ["Same", "Same"], "District": ["North", "South"],
                  "Latitude": [10, 20], "Data Acquisition Time": ["2024-01-01", "2024-02-01"],
                  "Potential of Hydrogen (pH)": [7.0, 8.0]}).to_csv(path, index=False)
    ambiguous = get_historical_profile(path, "groundwater", "Same", as_of="2024-03-01")
    assert ambiguous["match_level"] == "ambiguous" and ambiguous["sample_count"] == 0
    assert ambiguous["candidate_sample_count"] == 2 and ambiguous["parameters"] == {}
    assert "ambiguous_station_name" in ambiguous["data_quality_flags"]
    pd.DataFrame({"Station": ["Same", "Same", "Same"], "District": ["North", "North", "North"],
                  "Latitude": [10, 10, None], "Data Acquisition Time": ["2024-01-01", "2024-02-01", "2024-03-01"],
                  "Potential of Hydrogen (pH)": [7.0, 8.0, 7.5]}).to_csv(path, index=False)
    repeated = get_historical_profile(path, "groundwater", "Same", as_of="2024-03-01")
    assert repeated["match_level"] == "station" and repeated["sample_count"] == 3
    assert repeated["parameters"]["Potential of Hydrogen (pH)"]["measurement_count"] == 3


def test_cpcb_allowlist_and_categorical_observations(surface_water):
    result = get_historical_profile(surface_water, "surface_water", "River Station", as_of="2021-02-01")
    assert set(result["parameters"]) == set(MEASUREMENT_COLUMNS["surface_water"])
    assert "Unexpected Metadata" not in result["parameters"]
    assert result["parameters"]["Colour"]["observed_categories"] == {"Clear": 1, "Pale yellow": 1}
    assert result["parameters"]["Odour"]["observed_categories"] == {"Odourless": 2}
    assert result["parameters"]["Turbidity (NTU)"]["measurement_count"] == 0
    assert result["parameters"]["Turbidity (NTU)"]["mean"] is None


def test_missing_measurement_columns_reported_and_actual_allowlists_differ(groundwater, surface_water):
    gw = get_historical_profile(groundwater, "groundwater", "A Station")
    sw = get_historical_profile(surface_water, "surface_water", "River Station")
    assert set(gw["parameters"]).issubset(set(MEASUREMENT_COLUMNS["groundwater"]))
    assert set(sw["parameters"]).issubset(set(MEASUREMENT_COLUMNS["surface_water"]))
    assert "missing_measurement_columns" in gw["data_quality_flags"]


def test_complete_cgwb_schema_allowlist(tmp_path):
    path = tmp_path / "cgwb_schema.csv"
    columns = {
        "Station": ["G"], "Data Acquisition Time": ["01-01-2024 00:00"],
        "SlNo": [1], "District LGD Code": [10], "Latitude": [25.0], "Longitude": [80.0],
        "Unexpected Metadata": [100],
    }
    columns.update({name: [None] for name in MEASUREMENT_COLUMNS["groundwater"]})
    pd.DataFrame(columns).to_csv(path, index=False)
    result = get_historical_profile(path, "groundwater", "G", as_of="2024-02-01")
    assert set(result["parameters"]) == set(MEASUREMENT_COLUMNS["groundwater"])
    assert all(p["measurement_count"] == 0 and p["mean"] is None for p in result["parameters"].values())
    assert "Unexpected Metadata" not in result["parameters"]


def test_matched_unmatched_and_ambiguous_outputs_share_contract(groundwater, tmp_path):
    ambiguous_file = tmp_path / "ambiguous_contract.csv"
    pd.DataFrame({"Station": ["Name", "Name"], "District": ["One", "Two"],
                  "Data Acquisition Time": ["2024-01-01", "2024-02-01"],
                  "Potential of Hydrogen (pH)": [7.0, 8.0]}).to_csv(ambiguous_file, index=False)
    profiles = [
        get_historical_profile(groundwater, "groundwater", "A Station", as_of="2024-06-01"),
        get_historical_profile(groundwater, "groundwater", "nobody", as_of="2024-06-01"),
        get_historical_profile(ambiguous_file, "groundwater", "Name", as_of="2024-06-01"),
    ]
    assert all(set(profile) == set(profiles[0]) for profile in profiles)
    assert [profile["match_level"] for profile in profiles] == ["station", "unmatched", "ambiguous"]


def test_trace_metal_zeros_are_preserved_and_blanks_remain_missing(tmp_path):
    path = tmp_path / "zeros.csv"
    pd.DataFrame({
        "Station": ["Kadipur", "Kadipur"], "District": ["SULTANPUR", "SULTANPUR"],
        "Data Acquisition Time": ["25-05-2018 00:00", "30-05-2021 08:00"],
        "Total Dissolved Solids (mg/L)": [0, None],
        "Total Alkalinity (mg/L as CaCO3)": [0, None],
        "Iron(mg/L)": [0, None], "Arsenic (mg/L)": [0, None],
        "Lead (mg/L)": [None, None], "Carbonate (mg/L)": [None, 0],
    }).to_csv(path, index=False)

    result = get_historical_profile(path, "groundwater", "Kadipur", as_of="2021-05-30")
    params = result["parameters"]
    for name in ("Total Dissolved Solids (mg/L)", "Total Alkalinity (mg/L as CaCO3)", "Iron(mg/L)", "Arsenic (mg/L)", "Carbonate (mg/L)"):
        assert params[name]["measurement_count"] == 1
        assert params[name]["missing_count"] == 1
        assert params[name]["mean"] == 0.0
        assert params[name]["zero_count"] == 1
    assert params["Lead (mg/L)"]["measurement_count"] == 0
    assert params["Lead (mg/L)"]["missing_count"] == 2
    assert params["Lead (mg/L)"]["mean"] is None
    assert params["Lead (mg/L)"]["zero_count"] == 0
    diag = result["zero_value_diagnostics"]["trace_metal_parameters_with_zero_values"]
    assert diag == [{"parameter": "Iron(mg/L)", "zero_count": 1},
                    {"parameter": "Arsenic (mg/L)", "zero_count": 1}]
    assert "trace_metal_zero_values_unverified" in result["data_quality_flags"]
    caution = result["zero_value_diagnostics"]["caution"]
    assert "does not establish" in caution and "below a detection limit" in caution

    lead_zero_path = tmp_path / "lead_zero.csv"
    pd.DataFrame({"Station": ["Lead sample"], "Data Acquisition Time": ["2024-01-01"],
                  "Lead (mg/L)": [0]}).to_csv(lead_zero_path, index=False)
    lead_zero = get_historical_profile(lead_zero_path, "groundwater", "Lead sample", as_of="2024-02-01")
    assert lead_zero["zero_value_diagnostics"]["trace_metal_parameters_with_zero_values"] == [
        {"parameter": "Lead (mg/L)", "zero_count": 1}
    ]
