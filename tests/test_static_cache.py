"""``/data`` static serving: content types the census map relies on (#1266)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.static_cache import CachedStaticFiles


def test_geojson_served_as_geo_json(tmp_path: Path) -> None:
    (tmp_path / "place_01.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    (tmp_path / "manifest.json").write_text("{}")
    app = FastAPI()
    app.mount("/data", CachedStaticFiles(directory=tmp_path), name="data")
    client = TestClient(app)

    r = client.get("/data/place_01.geojson")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    assert "max-age" in r.headers["cache-control"]

    assert client.get("/data/manifest.json").headers["content-type"].startswith("application/json")
