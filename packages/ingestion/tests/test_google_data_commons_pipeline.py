"""Unit tests for the Google Data Commons jurisdiction-enrichment port."""
from __future__ import annotations

import json

import pytest

import ingestion.google_data_commons.client as client_mod
from ingestion.google_data_commons.bronze import (
    TABLE,
    VAR_COLUMNS,
    _INSERT_SQL,
    to_record,
)
from ingestion.google_data_commons.client import DataCommonsClient


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    """Stand-in for httpx.Client capturing the last POST body."""

    last_body: dict | None = None

    def __init__(self, payload: dict):
        self._payload = payload

    def __call__(self, *args, **kwargs):  # used as the httpx.Client factory
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):  # noqa: A002 - mirror httpx
        type(self).last_body = json
        return _FakeResponse(self._payload)


def _payload(**values: float) -> dict:
    """Build a v2-observation-shaped payload for geoId/01073."""
    by_variable = {}
    for var, val in values.items():
        by_variable[var] = {
            "byEntity": {
                "geoId/01073": {
                    "orderedFacets": [
                        {"facetId": "src", "observations": [{"date": "2022", "value": val}]}
                    ]
                }
            }
        }
    return {"byVariable": by_variable, "facets": {}}


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("DATA_COMMONS_API_KEY", raising=False)
    with pytest.raises(ValueError):
        DataCommonsClient()


def test_get_place_dcid():
    c = DataCommonsClient(api_key="k")
    assert c.get_place_dcid("01073") == "geoId/01073"
    assert c.get_place_dcid("0107000", "City") == "geoId/0107000"


def test_enrich_jurisdiction_parses_v2(monkeypatch):
    fake = _FakeClient(_payload(Count_Person=658573, Median_Income_Household=65000))
    monkeypatch.setattr(client_mod.httpx, "Client", fake)

    c = DataCommonsClient(api_key="k")
    data = c.enrich_jurisdiction("01073", variables=["Count_Person", "Median_Income_Household"])

    assert data["fips_code"] == "01073"
    assert data["dcid"] == "geoId/01073"
    assert data["data_source"] == "Google Data Commons"
    assert data["Count_Person"] == 658573
    assert data["Median_Income_Household"] == 65000
    # The POST body carries the key via header path; request shape is correct.
    assert _FakeClient.last_body["entity"]["dcids"] == ["geoId/01073"]
    assert "Count_Person" in _FakeClient.last_body["variable"]["dcids"]


def test_enrich_missing_var_is_none(monkeypatch):
    fake = _FakeClient(_payload(Count_Person=100))
    monkeypatch.setattr(client_mod.httpx, "Client", fake)

    c = DataCommonsClient(api_key="k")
    data = c.enrich_jurisdiction("01073", variables=["Count_Person", "Median_Age_Person"])
    assert data["Count_Person"] == 100
    assert data["Median_Age_Person"] is None


def test_enrich_bulk_returns_one_row_per_fips(monkeypatch):
    fake = _FakeClient(_payload(Count_Person=658573))
    monkeypatch.setattr(client_mod.httpx, "Client", fake)

    c = DataCommonsClient(api_key="k")
    rows = c.enrich_jurisdictions_bulk(["01073", "01089"], variables=["Count_Person"])
    assert len(rows) == 2
    assert [r["fips_code"] for r in rows] == ["01073", "01089"]
    # 01073 has data; 01089 absent from payload -> None
    assert rows[0]["Count_Person"] == 658573
    assert rows[1]["Count_Person"] is None


def test_to_record_maps_statvars_to_columns():
    enriched = {
        "fips_code": "01073",
        "dcid": "geoId/01073",
        "data_source": "Google Data Commons",
        "retrieval_date": "2026-06-06T00:00:00+00:00",
        "Count_Person": 658573,
        "Median_Income_Household": 65000,
        "Median_Age_Person": None,
    }
    rec = to_record(enriched)
    assert rec["fips_code"] == "01073"
    assert rec["population"] == 658573
    assert rec["median_household_income"] == 65000
    assert rec["median_age"] is None
    # stats JSONB keeps only non-null statvars, keyed by raw DCID name
    stats = json.loads(rec["stats"])
    assert stats["Count_Person"] == 658573
    assert "Median_Age_Person" not in stats


def test_var_columns_cover_all_vars():
    # Every statistical variable in the catalog maps to a typed column.
    assert set(VAR_COLUMNS) == set(DataCommonsClient.ALL_VARS)
    # Column names are unique.
    assert len(set(VAR_COLUMNS.values())) == len(VAR_COLUMNS)


def test_insert_sql_targets_bronze_table():
    sql = str(_INSERT_SQL)
    assert TABLE in sql
    assert "ON CONFLICT (fips_code) DO UPDATE" in sql
