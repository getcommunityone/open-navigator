"""Tracker lead loader (#956): parsing and refusal handling. No network, no database."""

from __future__ import annotations

import json

import httpx
import pytest
from ingestion.data_centers import load_hearing_tracker_leads as mod


def test_datacenterfights_reads_only_the_meetings_list() -> None:
    body = json.dumps(
        {
            "projects": [{"id": "p1"}],
            "meetings": [
                {
                    "id": "avery-nc-2026-11-02",
                    "date": "2026-11-02",
                    "source": "https://averycountync.gov/x",
                },
                {"date": "2026-12-01"},  # no id: skipped
            ],
        }
    ).encode()
    rows = mod.parse_datacenterfights(body)
    assert [rid for rid, _ in rows] == ["avery-nc-2026-11-02"]
    assert rows[0][1]["source"] == "https://averycountync.gov/x"


def test_sitingradar_rows_keyed_by_item_id_with_bom() -> None:
    body = (
        "﻿item_id,state,jurisdiction,census_geoid,event_date,sectors,source_url\n"
        "54254,MI,Groveland Township,2612535640,2026-11-30,data_center,https://example.gov/n\n"
        ",MI,No id,,2026-12-01,data_center,\n"
    ).encode()
    rows = mod.parse_sitingradar(body)
    assert [rid for rid, _ in rows] == ["54254"]
    assert rows[0][1]["census_geoid"] == "2612535640"


class _Fetcher:
    def __init__(self, resp=None, err: Exception | None = None):
        self.resp, self.err, self.urls = resp, err, []

    def get(self, url):
        self.urls.append(url)
        if self.err:
            raise self.err
        return self.resp


def test_fetch_uses_the_published_file_and_raises_on_http_error() -> None:
    tracker = mod.TRACKERS["sitingradar"]
    ok = _Fetcher(httpx.Response(200, content=b"item_id,state\n1,OH\n"))
    assert mod.fetch_tracker(ok, tracker) == [("1", {"item_id": "1", "state": "OH"})]
    assert ok.urls == ["https://sitingradar.com/data/siting-radar-upcoming.csv"]
    with pytest.raises(RuntimeError, match="HTTP 503"):
        mod.fetch_tracker(_Fetcher(httpx.Response(503)), tracker)


def test_robots_refusal_propagates() -> None:
    with pytest.raises(PermissionError):
        mod.fetch_tracker(
            _Fetcher(err=PermissionError("robots.txt disallows")),
            mod.TRACKERS["datacenterfights"],
        )


def test_dry_run_needs_no_database(monkeypatch) -> None:
    monkeypatch.setattr(mod, "fetch_tracker", lambda f, t: [("1", {})])
    monkeypatch.delenv("NEON_DATABASE_URL_DEV", raising=False)
    assert mod.main(["--dry-run"]) == 0
    assert mod.main([]) == 2  # a real run needs the dev / local DSN
