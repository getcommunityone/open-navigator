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
    assert delete_sql.startswith(f"DELETE FROM {_TABLE} WHERE jurisdiction_id = %s AND NOT")
    assert "suiteone:" in delete_sql and "suiteone_listing" in delete_sql
    assert params == (_JID,)
    (insert_sql, _rows), = batches
    assert "ON CONFLICT (jurisdiction_id, url_sha256) DO NOTHING" in insert_sql


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL (a disposable Postgres)")
def test_reload_keeps_suiteone_rows_in_postgres(tmp_path: Path) -> None:
    import psycopg2

    ddl = (
        Path(__file__).resolve().parents[1]
        / "packages/hosting/scripts/neon/migrations/020_recreate_bronze_events_meetings_scraped_link_document.sql"
    ).read_text(encoding="utf-8")
    conn = psycopg2.connect(os.environ["TEST_DATABASE_URL"])
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
        manifest = _manifest([_SUITEONE_URL, "https://example.org/crawl.pdf"])
        loader._load_manifest_to_table(conn, _TABLE, manifest, tmp_path / "_manifest.json", tmp_path)
        loader._load_manifest_to_table(conn, _TABLE, manifest, tmp_path / "_manifest.json", tmp_path)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT url, meeting_date_source FROM {_TABLE} WHERE jurisdiction_id = %s ORDER BY url", (_JID,)
            )
            rows = cur.fetchall()
    finally:
        conn.rollback()
        conn.close()

    assert rows == [
        ("https://example.org/crawl.pdf", None),
        (_SUITEONE_URL, "suiteone_listing"),
        ("https://x.org/retagged.pdf", "suiteone_listing"),
    ]
