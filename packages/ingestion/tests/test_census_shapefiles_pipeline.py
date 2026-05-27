"""Unit tests for the Census shapefiles pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from ingestion.census.shapefiles import (  # noqa: E402
    TYPES,
    CensusShapefilesPipeline,
    ShapefileRow,
    find_shp,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _square(x: float, y: float) -> Polygon:
    return Polygon([(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)])


def _write_states_shp(directory: Path) -> Path:
    """Write a synthetic 'states' shapefile mirroring Census CB column names."""
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": ["01", "02"],
            "STATEFP": ["01", "02"],
            "STATENS": ["01779775", "01785533"],
            "GEOIDFQ": ["0400000US01", "0400000US02"],
            "STUSPS": ["AL", "AK"],
            "NAME": ["Alabama", "Alaska"],
            "LSAD": ["00", "00"],
            "ALAND": [131174048583, 1477946266785],
            "AWATER": [4593327154, 245390495931],
            "geometry": [_square(0, 0), _square(2, 2)],
        },
        crs="EPSG:4269",
    )
    shp_path = directory / "cb_2025_us_state_500k.shp"
    gdf.to_file(shp_path)
    return shp_path


def test_zip_patterns_cover_all_types():
    from ingestion.census.shapefiles import ZIP_PATTERNS

    assert set(ZIP_PATTERNS) == set(TYPES)
    assert ZIP_PATTERNS["states"].format(year=2025) == "cb_2025_us_state_500k.zip"


def test_states_row_fn_builds_expected_params():
    row_fn = TYPES["states"]["row_fn"]
    geom = _square(0, 0)
    row = {
        "GEOID": "01",
        "STATEFP": "01",
        "STATENS": "01779775",
        "GEOIDFQ": "0400000US01",
        "STUSPS": "AL",
        "NAME": "Alabama",
        "LSAD": "00",
        "ALAND": 131174048583,
        "AWATER": 4593327154,
        "geometry": geom,
    }
    params = row_fn(row, 2025)
    assert params["geoid"] == "01"
    assert params["aland"] == 131174048583
    assert isinstance(params["aland"], int)
    assert params["geom_wkt"] == geom.wkt
    assert params["vintage_year"] == "2025"


def test_zcta_row_fn_handles_optional_numeric_and_null_geometry():
    row_fn = TYPES["zcta"]["row_fn"]
    row = {
        "GEOID20": "00601",
        "ZCTA5CE20": "00601",
        "GEOIDFQ20": None,
        "CLASSFP20": "B5",
        "MTFCC20": "G6350",
        "FUNCSTAT20": "S",
        "ALAND20": "164923353",
        "AWATER20": None,
        "INTPTLAT20": "18.18",
        "INTPTLON20": None,
        "geometry": None,
    }
    params = row_fn(row, 2024)
    assert params["geoid20"] == "00601"
    assert params["aland20"] == 164923353
    assert params["awater20"] is None
    assert params["intptlat20"] == pytest.approx(18.18)
    assert params["intptlon20"] is None
    assert params["geom_wkt"] is None


def test_shapefile_row_schema_accepts_valid_row():
    r = ShapefileRow(
        source="census_shapefiles",
        source_version="2025",
        natural_key="states:01",
        shapefile_type="states",
        table="bronze.bronze_geo_states",
        values={"geoid": "01", "geom_wkt": "POLYGON((0 0,1 0,1 1,0 1,0 0))"},
    )
    assert r.shapefile_type == "states"
    assert r.values["geoid"] == "01"


def test_shapefile_row_schema_rejects_extra_field():
    with pytest.raises(Exception):
        ShapefileRow(
            source="census_shapefiles",
            source_version="2025",
            natural_key="states:01",
            shapefile_type="states",
            table="bronze.bronze_geo_states",
            values={"geoid": "01"},
            unexpected="boom",  # extra="forbid" on RawRow
        )


def test_pipeline_metadata():
    p = CensusShapefilesPipeline()
    assert p.source == "census_shapefiles"
    assert p.batch_size == 500
    assert p.row_schema is ShapefileRow


def test_find_shp_returns_none_when_zip_missing(tmp_path, monkeypatch):
    import ingestion.census.shapefiles as sp

    monkeypatch.setattr(sp, "CACHE_DIR", tmp_path)
    assert find_shp(2025, "states") is None


def test_extract_roundtrip_and_validate(tmp_path):
    shp_path = _write_states_shp(tmp_path)
    p = CensusShapefilesPipeline(year=2025, types=["states"], path=shp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    first = extracted[0]
    assert first["source"] == "census_shapefiles"
    assert first["source_version"] == "2025"
    assert first["natural_key"] == "states:01"
    assert first["shapefile_type"] == "states"
    assert first["table"] == "bronze.bronze_geo_states"
    assert first["values"]["name"] == "Alabama"
    assert first["values"]["geom_wkt"].startswith("POLYGON")

    # All extracted rows validate cleanly into ShapefileRow.
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_limit_caps_rows(tmp_path):
    shp_path = _write_states_shp(tmp_path)
    p = CensusShapefilesPipeline(year=2025, types=["states"], path=shp_path, limit=1)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    assert extracted[0]["natural_key"] == "states:01"
