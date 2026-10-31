from __future__ import annotations

import csv

import pytest
from fastapi.testclient import TestClient

from backend.api.routes import historical as historical_route
from backend.config import Settings
from backend.main import create_app


def _write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def historical_datasets(tmp_path, monkeypatch):
    groundwater_path = tmp_path / "cgwb_test.csv"
    groundwater_columns = [
        "Station",
        "Village",
        "Block",
        "Tehsil",
        "District",
        "Data Acquisition Time",
        "Potential of Hydrogen (pH)",
        "Arsenic (mg/L)",
    ]
    groundwater_rows = [
        {
            "Station": "Aandwa",
            "Village": "Aandwa",
            "Block": "Block One",
            "Tehsil": "Tehsil One",
            "District": "District One",
            "Data Acquisition Time": "25-05-2004",
            "Potential of Hydrogen (pH)": "7.2",
            "Arsenic (mg/L)": "0.01",
        },
        {
            "Station": "Aandwa",
            "Village": "Aandwa",
            "Block": "Block One",
            "Tehsil": "Tehsil One",
            "District": "District One",
            "Data Acquisition Time": "26-05-2004",
            "Potential of Hydrogen (pH)": "7.4",
            "Arsenic (mg/L)": "",
        },
        {
            "Station": "Shared Station",
            "Village": "Shared Village",
            "Block": "Block Two",
            "Tehsil": "Tehsil Two",
            "District": "District Alpha",
            "Data Acquisition Time": "10-01-2024",
            "Potential of Hydrogen (pH)": "7.1",
            "Arsenic (mg/L)": "0.02",
        },
        {
            "Station": "Shared Station",
            "Village": "Shared Village",
            "Block": "Block Two",
            "Tehsil": "Tehsil Two",
            "District": "District Beta",
            "Data Acquisition Time": "11-01-2024",
            "Potential of Hydrogen (pH)": "7.3",
            "Arsenic (mg/L)": "0.03",
        },
    ]
    _write_csv(groundwater_path, groundwater_columns, groundwater_rows)

    surface_water_path = tmp_path / "cpcb_test.csv"
    surface_water_columns = [
        "Station",
        "River",
        "District",
        "Data Acquisition Time",
        "Electric Conductivity (μS/cm)",
        "Colour",
        "Odour",
        "Turbidity (NTU)",
        "Temperature (ºC)",
        "Total Solids (mg/L)",
    ]
    surface_water_rows = [
        {
            "Station": "YAMUNA AT AGRA U/S U.P.",
            "River": "Yamuna",
            "District": "Agra",
            "Data Acquisition Time": "2021-01-13",
            "Electric Conductivity (μS/cm)": "850",
            "Colour": "Brown",
            "Odour": "Odourless",
            "Turbidity (NTU)": "5.0",
            "Temperature (ºC)": "20",
            "Total Solids (mg/L)": "500",
        },
        {
            "Station": "YAMUNA AT AGRA U/S U.P.",
            "River": "Yamuna",
            "District": "Agra",
            "Data Acquisition Time": "2021-03-08",
            "Electric Conductivity (μS/cm)": "900",
            "Colour": "Brown",
            "Odour": "Odourless",
            "Turbidity (NTU)": "6.0",
            "Temperature (ºC)": "21",
            "Total Solids (mg/L)": "520",
        },
    ]
    _write_csv(surface_water_path, surface_water_columns, surface_water_rows)

    monkeypatch.setitem(
        historical_route.DATASET_PATHS, "groundwater", groundwater_path
    )
    monkeypatch.setitem(
        historical_route.DATASET_PATHS, "surface_water", surface_water_path
    )
    return {
        "groundwater": groundwater_path,
        "surface_water": surface_water_path,
    }


def _client(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "historical-api-test.sqlite3"),
        device_tokens={},
        sampling_interval_seconds=10,
        device_stale_after_seconds=120,
        aggregation_late_arrival_seconds=0,
        aggregation_min_valid_coverage=0.0,
        aggregation_poll_seconds=60,
    )
    return TestClient(create_app(settings, start_aggregation_worker=False))


def test_groundwater_locations_are_returned_with_deduplicated_match_fields(
    tmp_path, historical_datasets
):
    with _client(tmp_path) as client:
        response = client.get(
            "/api/v1/locations", params={"source_type": "groundwater"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["agency"] == "CGWB"
    assert body["source_type"] == "groundwater"
    assert body["total_locations"] > 0

    aandwa = next(
        item for item in body["locations"] if item["location_id"] == "Aandwa"
    )
    assert aandwa["match_fields"] == ["Station", "Village"]
    assert len(aandwa["match_fields"]) == len(set(aandwa["match_fields"]))


def test_surface_water_locations_are_returned_from_cpcb_dataset(
    tmp_path, historical_datasets
):
    with _client(tmp_path) as client:
        response = client.get(
            "/api/v1/locations", params={"source_type": "surface_water"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["agency"] == "CPCB"
    assert body["source_type"] == "surface_water"
    assert body["total_locations"] > 0
    assert any(
        item["location_id"] == "YAMUNA AT AGRA U/S U.P."
        for item in body["locations"]
    )


def test_groundwater_profile_uses_existing_cgwb_engine(
    tmp_path, historical_datasets
):
    with _client(tmp_path) as client:
        response = client.get(
            "/api/v1/historical-context",
            params={"source_type": "groundwater", "location_id": "Aandwa"},
        )

    assert response.status_code == 200
    body = response.json()
    profile = body["profile"]
    assert body["dataset"]["agency"] == "CGWB"
    assert body["dataset"]["historical_data_only"] is True
    assert profile["match_level"] == "station"
    assert profile["sample_count"] == 2
    ph = profile["parameters"]["Potential of Hydrogen (pH)"]
    assert ph["measurement_count"] == 2
    assert ph["mean"] == pytest.approx(7.3)


def test_surface_water_profile_uses_existing_cpcb_engine(
    tmp_path, historical_datasets
):
    with _client(tmp_path) as client:
        response = client.get(
            "/api/v1/historical-context",
            params={
                "source_type": "surface_water",
                "location_id": "YAMUNA AT AGRA U/S U.P.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    profile = body["profile"]
    assert body["dataset"]["agency"] == "CPCB"
    assert profile["match_level"] == "station"
    assert profile["sample_count"] == 2
    turbidity = profile["parameters"]["Turbidity (NTU)"]
    assert turbidity["measurement_count"] == 2
    assert turbidity["mean"] == pytest.approx(5.5)


def test_unmatched_location_is_reported_without_inventing_measurements(
    tmp_path, historical_datasets
):
    with _client(tmp_path) as client:
        response = client.get(
            "/api/v1/historical-context",
            params={"source_type": "groundwater", "location_id": "No Such Place"},
        )

    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["match_level"] == "unmatched"
    assert profile["sample_count"] == 0
    assert profile["parameters"] == {}
    assert "unmatched_location" in profile["data_quality_flags"]


def test_ambiguous_station_name_is_reported_without_aggregating_candidates(
    tmp_path, historical_datasets
):
    with _client(tmp_path) as client:
        response = client.get(
            "/api/v1/historical-context",
            params={
                "source_type": "groundwater",
                "location_id": "Shared Station",
            },
        )

    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["match_level"] == "ambiguous"
    assert profile["sample_count"] == 0
    assert profile["candidate_sample_count"] == 2
    assert profile["parameters"] == {}
    assert "ambiguous_station_name" in profile["data_quality_flags"]
    assert len(profile["ambiguous_candidates"]) == 2


def test_invalid_source_type_is_rejected(tmp_path, historical_datasets):
    with _client(tmp_path) as client:
        locations = client.get(
            "/api/v1/locations", params={"source_type": "river_water"}
        )
        profile = client.get(
            "/api/v1/historical-context",
            params={"source_type": "river_water", "location_id": "Aandwa"},
        )

    assert locations.status_code == 422
    assert profile.status_code == 422


def test_missing_dataset_returns_service_unavailable(tmp_path, monkeypatch):
    missing_path = tmp_path / "does-not-exist.csv"
    monkeypatch.setitem(
        historical_route.DATASET_PATHS, "groundwater", missing_path
    )

    with _client(tmp_path) as client:
        locations = client.get(
            "/api/v1/locations", params={"source_type": "groundwater"}
        )
        profile = client.get(
            "/api/v1/historical-context",
            params={"source_type": "groundwater", "location_id": "Aandwa"},
        )

    assert locations.status_code == 503
    assert profile.status_code == 503
