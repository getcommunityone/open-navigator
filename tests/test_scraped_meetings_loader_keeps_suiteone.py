"""Reloading crawl manifests must not delete SuiteOne rows for the same jurisdiction (#393)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Self

import pytest

from scripts.discovery import load_scraped_meetings_manifests_to_bronze as loader

_TABLE = "bronze.bronze_events_meetings_municipalities_scraped"
_JID = "tuscaloosa_0177256"
_SUITEONE_URL = "https://tuscaloosaal.suiteonemedia.com/event/GetAgendaFile/1"


def _manifest(urls: list[str]) -> dict[str, Any]:
    return {
        "jurisdiction_id": _JID,
        "state": "AL",
        "scraped_at": "2026-11-01T00:00:00Z",
        "homepage_url": "https://www.tuscaloosa.com",
        "pages_fetched": [],
        "pdfs": [{"url": u, "anchor_text": "Agenda", "doc_type": "agenda"} for u in urls],
    }


class _RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.statements.append((sql, params))

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _RecordingConn:
    def __init__(self) -> None:
        self.cur = _RecordingCursor()

    def cursor(self) -> _RecordingCursor:
        return self.cur


def test_delete_spares_suiteone_rows_and_insert_skips_conflicts(monkeypatch, tmp_path: Path) -> None:
    batches: list[tuple[str, list]] = []
    monkeypatch.setattr(loader, "execute_batch", lambda cur, sql, rows, page_size: batches.append((sql, rows)))
    conn = _RecordingConn()

    n = loader._load_manifest_to_table(
        conn, _TABLE, _manifest(["https://example.org/a.pdf"]), tmp_path / "_manifest.json", tmp_path
    )

    assert n == 1
    (delete_sql, params), = conn.cur.statements
    assert delete_sql == (
        f"DELETE FROM {_TABLE} WHERE jurisdiction_id = %s AND NOT "
        "(COALESCE(manifest_relative_path, '') LIKE 'suiteone:%%' "
        "OR COALESCE(meeting_date_source, '') = 'suiteone_listing')"
    )  # %% is psycopg2's escape for a literal %, since the statement is parameterized
    assert params == (_JID,)
    (insert_sql, _rows), = batches
    assert "ON CONFLICT (jurisdiction_id, url_sha256) DO NOTHING" in insert_sql


def test_suiteone_upsert_claims_a_row_the_crawl_loaded_first() -> None:
    from scrapers.suiteone import scrape

    assert "manifest_relative_path = EXCLUDED.manifest_relative_path" in scrape._UPSERT


def _disposable_dsn() -> str:
    """TEST_DATABASE_URL, only when its database name ends in 'test'.

    Migration 020 commits its own DROP ... CASCADE of the scraped-meeting tables, so
    this test must never run against a real warehouse.
    """
    dsn = os.getenv("TEST_DATABASE_URL", "")
    if not dsn.rsplit("/", 1)[-1].split("?", 1)[0].endswith("test"):
        pytest.skip("needs TEST_DATABASE_URL naming a disposable database whose name ends in 'test'")
    return dsn


@pytest.mark.live
def test_reload_keeps_suiteone_rows_in_postgres(tmp_path: Path) -> None:
    import psycopg2
    from psycopg2.extras import execute_values
    from scrapers.suiteone import scrape

    ddl = (
        Path(__file__).resolve().parents[1]
        / "packages/hosting/scripts/neon/migrations/020_recreate_bronze_events_meetings_scraped_link_document.sql"
    ).read_text(encoding="utf-8")
    conn = psycopg2.connect(_disposable_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
            cur.execute(ddl)
            # One SuiteOne row (as scrapers.suiteone.scrape writes it) and one row the
            # SuiteOne upsert re-tagged after the crawl inserted it first.
            for url, path in ((_SUITEONE_URL, f"suiteone:{_JID}"), ("https://x.org/retagged.pdf", "data/m.json")):
                cur.execute(
                    f"INSERT INTO {_TABLE} (jurisdiction_id, state_code, census_geoid, manifest_relative_path,"
                    " manifest_scraped_at, resource_category, resource_kind, url, url_sha256, meeting_date_source)"
                    " VALUES (%s, 'AL', '0177256', %s, now(), 'document', 'pdf', %s, %s, 'suiteone_listing')",
                    (_JID, path, url, loader._sha256_url(url)),
                )
        claimed = "https://example.org/claimed.pdf"
        manifest = _manifest([_SUITEONE_URL, "https://example.org/crawl.pdf", claimed])
        loader._load_manifest_to_table(conn, _TABLE, manifest, tmp_path / "_manifest.json", tmp_path)
        # The SuiteOne scraper then lands a URL the crawl loaded first (real upsert SQL).
        with conn.cursor() as cur:
            execute_values(cur, scrape._UPSERT, [(
                _JID, "AL", "0177256", None, "2026-11-01T00:00:00Z", f"suiteone:{_JID}", "document", "pdf",
                claimed, loader._sha256_url(claimed), None, None, "agenda", "agenda", "[]",
                True, "2026-10-06", "suiteone_listing", "Finance Committee", "{}",
            )])
        loader._load_manifest_to_table(conn, _TABLE, manifest, tmp_path / "_manifest.json", tmp_path)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT url, meeting_date_source, manifest_relative_path FROM {_TABLE}"
                " WHERE jurisdiction_id = %s ORDER BY url",
                (_JID,),
            )
            rows = cur.fetchall()
    finally:
        conn.rollback()
        conn.close()

    manifest_path = "_manifest.json"  # stored relative to repo_root (tmp_path here)
    assert rows == [
        (claimed, "suiteone_listing", f"suiteone:{_JID}"),
        ("https://example.org/crawl.pdf", None, manifest_path),
        (_SUITEONE_URL, "suiteone_listing", f"suiteone:{_JID}"),
        ("https://x.org/retagged.pdf", "suiteone_listing", "data/m.json"),
    ]
