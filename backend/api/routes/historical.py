from __future__ import annotations

import logging
import sys
from datetime import date
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("aquasentinel.historical")

router = APIRouter(tags=["historical-context"])

# Resolve paths relative to the repository, not the terminal's working directory.
REPO_ROOT = Path(__file__).resolve().parents[3]

ENGINE_PATH = (
    REPO_ROOT
    / "historical-context"
    / "src"
    / "historical_context.py"
)

DATASET_PATHS = {
    "groundwater": (
        REPO_ROOT
        / "historical-context"
        / "datasets"
        / "raw"
        / "gwq_chemical_parameter_manual_cgwb_up_1961_2025.csv"
    ),
    "surface_water": (
        REPO_ROOT
        / "historical-context"
        / "datasets"
        / "raw"
        / "swq_physical_parameter_manual_cpcb_up_2021_2025.csv"
    ),
}

@lru_cache(maxsize=1)
def _historical_engine():
    """Load the existing historical engine without copying or rewriting it."""
    if not ENGINE_PATH.is_file():
        raise RuntimeError("Historical-context engine file is missing")

    spec = spec_from_file_location(
        "aquasentinel_historical_engine",
        ENGINE_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load historical-context engine")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def _dataset_path(source_type: str) -> Path:
    path = DATASET_PATHS[source_type]

    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"The configured {source_type} historical dataset is unavailable.",
        )

    return path


def _read_location_choices(source_type: str) -> list[dict]:
    """Read distinct location labels from the actual source dataset."""
    path = _dataset_path(source_type)
    engine = _historical_engine()

    try:
        header = pd.read_csv(path, nrows=0)
        available_columns = {
            str(column).strip().casefold(): str(column)
            for column in header.columns
        }

        matched_columns = {
            field: available_columns[field.casefold()]
            for field in engine.MATCH_COLUMNS
            if field.casefold() in available_columns
        }

        if not matched_columns:
            raise HTTPException(
                status_code=503,
                detail="The historical dataset has no supported location columns.",
            )

        df = pd.read_csv(
            path,
            usecols=list(matched_columns.values()),
            dtype="string",
            low_memory=False,
        )

    except HTTPException:
        raise
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError) as exc:
        logger.exception("Could not read historical location choices")
        raise HTTPException(
            status_code=503,
            detail="Unable to read the historical location dataset.",
        ) from exc

    locations: dict[str, dict] = {}

    for field, column in matched_columns.items():
        for raw_value in df[column].dropna():
            name = str(raw_value).strip()

            if not name or name == "-":
                continue

            key = name.casefold()

            if key not in locations:
                locations[key] = {
                    "location_id": name,
                    "name": name,
                    "match_fields": [],
                }

            locations[key]["match_fields"].append(field)

    result = list(locations.values())

    for item in result:
        item["match_fields"] = sorted(
            set(item["match_fields"]),
            key=lambda value: engine.MATCH_COLUMNS.index(value),
        )

    result.sort(key=lambda item: item["name"].casefold())

    return result


@router.get("/locations")
def historical_locations(
    source_type: Literal["groundwater", "surface_water"] = Query(...),
):
    """Return real location choices present in the selected historical dataset."""
    engine = _historical_engine()
    locations = _read_location_choices(source_type)

    return {
        "source_type": source_type,
        "agency": engine.SOURCE_DATASETS[source_type],
        "dataset_file": DATASET_PATHS[source_type].name,
        "historical_data_only": True,
        "match_order": list(engine.MATCH_COLUMNS),
        "total_locations": len(locations),
        "locations": locations,
    }


@router.get("/historical-context")
def historical_context(
    source_type: Literal["groundwater", "surface_water"] = Query(...),
    location_id: str = Query(min_length=1, max_length=160),
    as_of: date | None = Query(default=None),
):
    """
    Retrieve a historical profile using the existing CGWB/CPCB analysis engine.

    location_id is the exact location text returned by /locations.
    It is not a geographical ID or a guarantee of geographical proximity.
    """
    engine = _historical_engine()
    path = _dataset_path(source_type)

    try:
        profile = engine.get_historical_profile(
            path,
            source_type,
            location_id,
            as_of=as_of,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="The historical dataset is unavailable.",
        ) from exc

    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        logger.exception("Historical profile generation failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to process the historical dataset.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "dataset": {
            "source_type": source_type,
            "agency": engine.SOURCE_DATASETS[source_type],
            "file_name": path.name,
            "historical_data_only": True,
        },
        "profile": profile,
    }
