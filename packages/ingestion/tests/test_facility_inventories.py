"""Open data center inventories loader (#958): parsing, header checks, refusals. No network, no DB."""

from __future__ import annotations

import httpx
import pytest
from ingestion.data_centers import facility_inventories as mod

REGISTRY = mod.INVENTORIES["registry"]


def _registry_csv(*rows: str) -> bytes:
    head = "id,name,status,state,latitude,longitude,profile_url,city"
    return ("﻿" + "\n".join((head, *rows)) + "\n").encode()


def test_rows_keyed_by_source_id_and_trimmed() -> None:
    body = _registry_csv(
        "a-tx,  Alpha DC ,operational,TX,30.1,-97.7,https://suedatacenters.org/data-centers/a-tx,Austin",
        ",No id,proposed,TX,30,-97,https://x,Nowhere",
    )
    rows = mod.parse_csv(body, REGISTRY)
    assert [rid for rid, _ in rows] == ["a-tx"]
    assert rows[0][1]["name"] == "Alpha DC" and rows[0][1]["city"] == "Austin"


def test_missing_header_stops_with_what_was_found() -> None:
    with pytest.raises(mod.HeaderMismatch, match="profile_url"):
        mod.parse_csv(
            b"id,name,status,state,latitude,longitude\n1,a,b,TX,1,2\n", REGISTRY
        )


class _Fetcher:
    def __init__(self, resp=None, err: Exception | None = None):
        self.resp, self.err, self.urls = resp, err, []

    def get(self, url):
        self.urls.append(url)
        if self.err:
            raise self.err
        return self.resp


def test_fetch_reads_the_published_file_and_raises_on_http_error() -> None:
    ok = _Fetcher(
        httpx.Response(
            200, content=_registry_csv("b-va,B,planned,VA,38,-77,https://x,Ashburn")
        )
    )
    assert [rid for rid, _ in mod.fetch_inventory(ok, REGISTRY)] == ["b-va"]
    assert ok.urls == ["https://suedatacenters.org/data-centers.csv"]
    with pytest.raises(RuntimeError, match="HTTP 404"):
        mod.fetch_inventory(_Fetcher(httpx.Response(404)), REGISTRY)
    with pytest.raises(PermissionError):
        mod.fetch_inventory(_Fetcher(err=PermissionError("robots.txt")), REGISTRY)


def test_upsert_keeps_first_seen() -> None:
    sql = mod.upsert_sql(REGISTRY)
    update = sql.split("DO UPDATE SET", 1)[1]
    assert (
        "last_seen_at = EXCLUDED.last_seen_at" in update
        and "first_seen_at" not in update
    )


def test_dry_run_needs_no_database(monkeypatch) -> None:
    monkeypatch.setattr(mod, "fetch_inventory", lambda f, i: [("1", {})])
    monkeypatch.delenv("NEON_DATABASE_URL_DEV", raising=False)
    assert mod.main(["--dry-run"]) == 0
    assert mod.main([]) == 2
