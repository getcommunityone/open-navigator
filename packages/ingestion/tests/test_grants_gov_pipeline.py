"""Unit tests for the Grants.gov opportunities port (client + bronze loader)."""
from __future__ import annotations

import datetime as dt
import json

import ingestion.grants_gov.client as client_mod
from ingestion.grants_gov.bronze import (
    TABLE,
    _INSERT_SQL,
    parse_grants_date,
    to_record,
)
from ingestion.grants_gov.client import DATA_SOURCE, GrantsGovClient


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
    """Stand-in for httpx.Client returning a queue of payloads per POST."""

    last_body: dict | None = None

    def __init__(self, payloads: list[dict]):
        self._payloads = list(payloads)

    def __call__(self, *args, **kwargs):  # used as the httpx.Client factory
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):  # noqa: A002 - mirror httpx
        type(self).last_body = json
        payload = self._payloads.pop(0) if self._payloads else {"errorcode": 0, "data": {}}
        return _FakeResponse(payload)


def _search_payload(hits: list[dict], hit_count: int | None = None) -> dict:
    return {
        "errorcode": 0,
        "msg": "success",
        "data": {
            "hitCount": hit_count if hit_count is not None else len(hits),
            "oppHits": hits,
        },
    }


_HIT = {
    "id": "351234",
    "number": "HRSA-24-019",
    "title": "Oral Health Workforce",
    "agencyCode": "HHS-HRSA",
    "agency": "Health Resources and Services Administration",
    "openDate": "10/15/2024",
    "closeDate": "12/31/2024",
    "oppStatus": "posted",
    "docType": "synopsis",
    "cfdaList": ["93.110"],
}


# --- client ------------------------------------------------------------------


def test_search_opportunities_parses_response(monkeypatch):
    monkeypatch.setattr(client_mod.httpx, "Client", _FakeClient([_search_payload([_HIT])]))
    c = GrantsGovClient()
    resp = c.search_opportunities(keyword="oral health")
    assert resp["errorcode"] == 0
    assert resp["data"]["oppHits"][0]["id"] == "351234"
    # The POST body carries the search params.
    assert _FakeClient.last_body["keyword"] == "oral health"
    assert _FakeClient.last_body["oppStatuses"] == "forecasted|posted"


def test_iter_opportunities_paginates(monkeypatch):
    page1 = _search_payload([{"id": "1"}, {"id": "2"}], hit_count=3)
    page2 = _search_payload([{"id": "3"}], hit_count=3)
    monkeypatch.setattr(client_mod.httpx, "Client", _FakeClient([page1, page2]))
    c = GrantsGovClient()
    ids = [h["id"] for h in c.iter_opportunities(sleep=0)]
    assert ids == ["1", "2", "3"]


def test_iter_opportunities_respects_max_results(monkeypatch):
    page1 = _search_payload([{"id": "1"}, {"id": "2"}], hit_count=100)
    monkeypatch.setattr(client_mod.httpx, "Client", _FakeClient([page1]))
    c = GrantsGovClient()
    ids = [h["id"] for h in c.iter_opportunities(max_results=1, sleep=0)]
    assert ids == ["1"]


def test_iter_stops_on_api_error(monkeypatch):
    err = {"errorcode": 1, "msg": "bad request", "data": {}}
    monkeypatch.setattr(client_mod.httpx, "Client", _FakeClient([err]))
    c = GrantsGovClient()
    assert list(c.iter_opportunities(sleep=0)) == []


# --- bronze parsing ----------------------------------------------------------


def test_parse_grants_date_formats():
    assert parse_grants_date("12/31/2024") == dt.date(2024, 12, 31)
    assert parse_grants_date("2024-12-31") == dt.date(2024, 12, 31)
    assert parse_grants_date("2024-10-15T00:00:00Z") == dt.date(2024, 10, 15)
    assert parse_grants_date("") is None
    assert parse_grants_date(None) is None
    assert parse_grants_date("not-a-date") is None


def test_to_record_maps_search_fields():
    rec = to_record(_HIT)
    assert rec["opportunity_id"] == "351234"
    assert rec["opportunity_number"] == "HRSA-24-019"
    assert rec["title"] == "Oral Health Workforce"
    assert rec["agency_code"] == "HHS-HRSA"
    assert rec["agency_name"].startswith("Health Resources")
    assert rec["open_date"] == dt.date(2024, 10, 15)
    assert rec["close_date"] == dt.date(2024, 12, 31)
    assert rec["opp_status"] == "posted"
    assert rec["doc_type"] == "synopsis"
    assert rec["aln"] == "93.110"
    assert rec["data_source"] == DATA_SOURCE
    # raw keeps the full record verbatim.
    assert json.loads(rec["raw"])["id"] == "351234"


def test_to_record_legacy_field_fallbacks():
    legacy = {
        "id": "9",
        "opportunityNumber": "OLD-1",
        "opportunityTitle": "Legacy",
        "agencyName": "Old Agency",
        "opportunityStatus": "forecasted",
        "cfdaList": [{"cfdaNumber": "10.001"}],
    }
    rec = to_record(legacy)
    assert rec["opportunity_number"] == "OLD-1"
    assert rec["title"] == "Legacy"
    assert rec["agency_name"] == "Old Agency"
    assert rec["opp_status"] == "forecasted"
    assert rec["aln"] == "10.001"


def test_to_record_handles_missing_aln():
    rec = to_record({"id": "5", "title": "No ALN"})
    assert rec["aln"] is None
    assert rec["open_date"] is None


def test_insert_sql_targets_bronze_table():
    sql = str(_INSERT_SQL)
    assert TABLE in sql
    assert "ON CONFLICT (opportunity_id) DO UPDATE" in sql
