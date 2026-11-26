"""scrapers.meetings.doctext: text for crawled agenda/minutes PDFs (#392)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from scrapers.meetings import doctext


def test_select_covers_every_crawl_table_and_follows_the_staging_view() -> None:
    sql = doctext.build_select_sql(with_jurisdiction=False)
    for table in doctext.SCRAPED_TABLES:
        assert f"FROM {table} s" in sql
    assert sql.count("UNION ALL") == len(doctext.SCRAPED_TABLES) - 1
    assert "school_districts" not in sql  # not published yet (geoid collisions with places)
    # #1035: one rule: extract exactly what staging publishes (dates read from link text / file names included),
    # rather than a copy of its filter that drifts.
    assert "FROM staging.stg_scraped_meeting_documents g" in sql
    assert "g.url_sha256 = s.url_sha256" in sql
    assert "t.extraction_method <> 'error'" in sql  # failed downloads are retried
    assert "%(jurisdiction_id)s" not in sql
    assert "s.jurisdiction_id = %(jurisdiction_id)s" in doctext.build_select_sql(with_jurisdiction=True)


def test_cli_rejects_unpublished_doc_types() -> None:
    with pytest.raises(SystemExit):
        doctext.main(["--state", "AL", "--doc-types", "agenda,budget"])


def test_local_pdf_bytes_reads_only_real_pdfs(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "b.pdf").write_bytes(b"<html>not a pdf</html>")
    assert doctext.local_pdf_bytes("a.pdf", tmp_path) == b"%PDF-1.4 fake"
    assert doctext.local_pdf_bytes(str(tmp_path / "a.pdf"), Path("/nonexistent")) == b"%PDF-1.4 fake"
    assert doctext.local_pdf_bytes("b.pdf", tmp_path) is None
    assert doctext.local_pdf_bytes("missing.pdf", tmp_path) is None
    assert doctext.local_pdf_bytes(None, tmp_path) is None


def _disposable_dsn() -> str:
    """TEST_DATABASE_URL, only when its database name ends in 'test'.

    The test recreates the bronze scraped-meeting tables (the migration commits its
    own DROP ... CASCADE), so it must never point at a real warehouse.
    """
    dsn = os.getenv("TEST_DATABASE_URL", "")
    if not dsn.rsplit("/", 1)[-1].split("?", 1)[0].endswith("test"):
        pytest.skip("needs TEST_DATABASE_URL naming a disposable database whose name ends in 'test'")
    return dsn


@pytest.mark.live
def test_extract_writes_text_for_published_docs_only(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    import psycopg2

    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "Approve data center rezoning")
    pdf.save(tmp_path / "agenda.pdf")

    dsn = _disposable_dsn()
    ddl = (
        Path(__file__).resolve().parents[3]
        / "packages/hosting/scripts/neon/migrations/020_recreate_bronze_events_meetings_scraped_link_document.sql"
    ).read_text(encoding="utf-8")
    cols = (
        "jurisdiction_id, state_code, census_geoid, manifest_scraped_at, manifest_relative_path,"
        " resource_category, resource_kind, url, url_sha256, doc_type, meeting_date, meeting_date_source, local_path"
    )
    rows = [
        # published: day-dated agenda with the PDF still in the crawl cache
        ("bham_0107000", "data/m.json", "https://x.test/a.pdf", "a" * 64, "agenda", "2026-10-07", "anchor_text", "agenda.pdf"),
        # not published: year-only date
        ("bham_0107000", "data/m.json", "https://x.test/b.pdf", "b" * 64, "minutes", "2026-01-01", "manifest_year_only", None),
        # not ours: SuiteOne row
        ("bham_0107000", "suiteone:bham_0107000", "https://x.test/c.pdf", "c" * 64, "agenda", "2026-10-07", "suiteone_listing", None),
        # not ours: crawl's copy of a SuiteOne portal link
        ("bham_0107000", "data/m.json", "https://b.suiteonemedia.com/event/GetAgendaFile/1", "d" * 64, "agenda", "2026-10-07", "anchor_text", None),
    ]
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        cur.execute(ddl)
        cur.execute(f"DROP TABLE IF EXISTS {doctext._TEXT_TABLE}")
        for jid, path, url, sha, dt, md, src, lp in rows:
            cur.execute(
                f"INSERT INTO bronze.bronze_events_meetings_municipalities_scraped ({cols})"
                " VALUES (%s,'AL','0107000',now(),%s,'document','pdf',%s,%s,%s,%s,%s,%s)",
                (jid, path, url, sha, dt, md, src, lp),
            )
    conn.close()

    processed, with_text = doctext.extract(
        "AL", doc_types=["agenda", "minutes"], dsn=dsn, repo_root=tmp_path, sleep=0
    )
    again = doctext.extract("AL", doc_types=["agenda", "minutes"], dsn=dsn, repo_root=tmp_path, sleep=0)

    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        cur.execute(f"SELECT url_sha256, extraction_method, content FROM {doctext._TEXT_TABLE}")
        stored = cur.fetchall()
    conn.close()

    assert (processed, with_text) == (1, 1)
    assert again == (0, 0)  # resumable: nothing left to do
    assert len(stored) == 1
    sha, method, content = stored[0]
    assert sha == "a" * 64 and method == "pymupdf_text"
    assert "data center rezoning" in content
