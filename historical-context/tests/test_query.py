import json
from pathlib import Path

import query


def example_profile(**overrides):
    profile = {
        "source_type": "surface_water", "dataset_agency": "CPCB",
        "requested_location": "River Station", "match_level": "station",
        "matched_column": "Station", "sample_count": 2, "candidate_sample_count": 2,
        "earliest_sample_date": "2021-01-06", "latest_sample_date": "2021-01-07",
        "record_age_days": 10, "date_column": "Data Acquisition Time",
        "date_missing_count": 0,
        "parameters": {
            "Electric Conductivity (μS/cm)": {
                "unit": "μS/cm", "measurement_count": 1, "missing_count": 1,
                "mean": 10.0, "median": 10.0, "min": 10.0, "max": 10.0,
                "std": None, "observed_categories": None,
            },
            "Colour": {
                "unit": None, "measurement_count": 2, "missing_count": 0,
                "mean": None, "median": None, "min": None, "max": None,
                "std": None, "observed_categories": {"Clear": 2},
            },
        },
        "ambiguous_candidates": [], "measurement_columns_present": [],
        "zero_value_diagnostics": {
            "trace_metal_parameters_with_zero_values": [],
            "caution": "Its analytical meaning has not been verified; it does not establish contaminant absence or a below detection limit result.",
        },
        "measurement_columns_missing": [], "data_quality_flags": [],
        "geographic_proximity_established": False, "historical_data_only": True,
    }
    profile.update(overrides)
    return profile


def test_arguments_parse_source_location_as_of_csv_and_json(tmp_path):
    args = query.build_parser().parse_args([
        "--source", "groundwater", "--location", "Aandwa",
        "--as-of", "2024-01-31", "--csv", str(tmp_path / "input.csv"), "--json",
    ])
    assert args.source == "groundwater" and args.location == "Aandwa"
    assert args.as_of == "2024-01-31" and args.csv == tmp_path / "input.csv"
    assert args.json is True
    try:
        query.build_parser().parse_args([
            "--source", "groundwater", "--location", "Aandwa", "--as-of", "20240131",
        ])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("as-of must be written as YYYY-MM-DD")


def test_default_dataset_resolution_does_not_depend_on_cwd(monkeypatch, tmp_path, capsys):
    seen = {}

    def fake_profile(path, source, location, *, as_of=None):
        seen.update(path=path, source=source, location=location, as_of=as_of)
        return example_profile(source_type=source, requested_location=location)

    monkeypatch.setattr(query, "get_historical_profile", fake_profile)
    monkeypatch.chdir(tmp_path)
    assert query.main(["--source", "groundwater", "--location", "Aandwa"]) == 0
    assert seen["path"] == query.DEFAULT_CSVS["groundwater"].resolve()
    assert seen["path"].is_absolute()
    assert "Aandwa" in capsys.readouterr().out


def test_custom_csv_path_and_reference_date_are_forwarded(monkeypatch, tmp_path, capsys):
    custom = tmp_path / "custom.csv"
    custom.touch()
    seen = {}

    def fake_profile(path, source, location, *, as_of=None):
        seen.update(path=path, source=source, location=location, as_of=as_of)
        return example_profile()

    monkeypatch.setattr(query, "get_historical_profile", fake_profile)
    assert query.main([
        "--source", "surface_water", "--location", "River Station",
        "--as-of", "2024-01-31", "--csv", str(custom),
    ]) == 0
    assert seen == {
        "path": custom.resolve(), "source": "surface_water",
        "location": "River Station", "as_of": "2024-01-31",
    }
    assert "Dataset:" in capsys.readouterr().out


def test_readable_output_includes_statistics_categories_and_limitations(monkeypatch, capsys):
    monkeypatch.setattr(query, "get_historical_profile", lambda *a, **k: example_profile(data_quality_flags=["stale_record"]))
    assert query.main(["--source", "surface_water", "--location", "River Station"]) == 0
    out = capsys.readouterr().out
    for expected in (
        "Source agency: CPCB", "Match result: MATCHED", "Earliest valid sample date:",
        "Latest valid sample date:", "Valid measurements: 1", "Missing measurements: 1",
        "Mean: 10", "Median: 10", "Minimum: 10", "Maximum: 10",
        "WARNING: the latest available sample is more than 365 days old.",
        "Standard deviation: N/A", "Observed categories: Clear: 2",
        "historical observations", "does not prove geographic proximity",
        "does not determine whether water is safe or unsafe",
        "Trace-metal zero-value diagnostic:", "analytical meaning has not been verified",
    ):
        assert expected in out


def test_json_output_is_machine_readable(monkeypatch, capsys):
    monkeypatch.setattr(query, "get_historical_profile", lambda *a, **k: example_profile())
    assert query.main(["--source", "surface_water", "--location", "River Station", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["profile"]["dataset_agency"] == "CPCB"
    assert out["profile"]["parameters"]["Colour"]["observed_categories"] == {"Clear": 2}
    assert Path(out["dataset_path"]).is_absolute()


def test_missing_csv_and_invalid_arguments_have_clear_errors(tmp_path, capsys):
    missing = tmp_path / "missing.csv"
    assert query.main([
        "--source", "groundwater", "--location", "Aandwa", "--csv", str(missing),
    ]) == 2
    err = capsys.readouterr().err
    assert "Error:" in err and "Dataset not found" in err and "Traceback" not in err
    malformed = tmp_path / "malformed.csv"
    malformed.write_text("", encoding="utf-8")
    assert query.main([
        "--source", "groundwater", "--location", "Aandwa", "--csv", str(malformed),
    ]) == 2
    err = capsys.readouterr().err
    assert "no CSV header" in err and "Traceback" not in err
    try:
        query.main(["--source", "groundwater", "--location", "Aandwa", "--as-of", "01-02-2024"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("invalid reference date must be rejected")
    assert "valid YYYY-MM-DD date" in capsys.readouterr().err
    try:
        query.main(["--source", "other", "--location", "Aandwa"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("unsupported source must be rejected")
    assert "invalid choice" in capsys.readouterr().err


def test_unmatched_and_ambiguous_status_are_explained(monkeypatch, capsys):
    profile = example_profile(match_level="unmatched", matched_column=None, sample_count=0, parameters={},
                              data_quality_flags=["unmatched_location"])
    monkeypatch.setattr(query, "get_historical_profile", lambda *a, **k: profile)
    query.main(["--source", "surface_water", "--location", "Unknown"])
    assert "Match result: NO MATCH" in capsys.readouterr().out
    profile = example_profile(match_level="ambiguous", data_quality_flags=["ambiguous_station_name"],
                              ambiguous_candidates=[{"station": "River Station", "location": {"District": "A"},
                                                    "observation_count": 2}], candidate_sample_count=2)
    monkeypatch.setattr(query, "get_historical_profile", lambda *a, **k: profile)
    query.main(["--source", "surface_water", "--location", "River Station"])
    out = capsys.readouterr().out
    assert "Match result: AMBIGUOUS" in out
    assert "Candidate observations needing disambiguation: 2" in out
