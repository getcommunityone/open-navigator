"""DC-4.1 (#249): parsing Epoch AI's data center files for bronze."""

from __future__ import annotations

import json
from datetime import date

import pytest

from ingestion.data_centers.epoch_sites import (
    DATA_CENTERS,
    TIMELINES,
    HeaderMismatch,
    bronze_rows,
    create_sql,
    insert_sql,
    parse_csv,
)

SITES = "﻿Name,Owner,Country,Address\nSite A,Corp #likely,United States,\"1 Rd, Abilene, TX\"\n,,,\n"
TIMELINE = "Data center,Date,Construction status\nSite A,2026-01-01,Operational\n"


def test_parse_strips_bom_and_skips_blank_rows() -> None:
    rows = parse_csv(SITES, DATA_CENTERS)
    assert len(rows) == 1
    assert rows[0]["Name"] == "Site A" and rows[0]["Owner"] == "Corp #likely"


def test_missing_header_stops_with_what_was_found() -> None:
    with pytest.raises(HeaderMismatch) as e:
        parse_csv("Site,Owner\nA,B\n", DATA_CENTERS)
    assert "Name" in str(e.value) and "Site" in str(e.value)
    with pytest.raises(HeaderMismatch):
        parse_csv("Data center,When\nA,2026\n", TIMELINES)


def test_bronze_rows_keep_the_whole_record_and_the_source() -> None:
    rows = parse_csv(TIMELINE, TIMELINES)
    (row,) = bronze_rows(rows, TIMELINES, file_sha256="abc", snapshot_on=date(2026, 11, 15))
    sha, n, snap, url, key, record = row
    assert (sha, n, snap, key) == ("abc", 1, date(2026, 11, 15), "Site A")
    assert url == "https://epoch.ai/data/data_centers/data_center_timelines.csv"
    assert json.loads(record)["Construction status"] == "Operational"


def test_sql_is_idempotent_per_file() -> None:
    assert "PRIMARY KEY (file_sha256, row_number)" in create_sql(DATA_CENTERS)
    assert "ON CONFLICT (file_sha256, row_number) DO NOTHING" in insert_sql(TIMELINES)
    assert "data_center" in insert_sql(TIMELINES) and "name" in insert_sql(DATA_CENTERS)


def test_dsn_never_reads_neon_urls(monkeypatch) -> None:
    """#441: an exported production Neon URL must not receive bronze rows."""
    from ingestion.data_centers import epoch_sites

    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://u:p@ep-prod.neon.tech/db")
    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://u:p@ep-dev.neon.tech/db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    assert epoch_sites._dsn() == "postgresql://postgres:pw@localhost:5433/open_navigator"


def test_dsn_uses_postgres_database_url_or_explicit(monkeypatch) -> None:
    from ingestion.data_centers import epoch_sites

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.local:5433/x")
    assert epoch_sites._dsn() == "postgresql://u:p@db.local:5433/x"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./users.db")  # the legacy user DB is ignored
    assert "localhost:5433" in epoch_sites._dsn()
    assert epoch_sites._dsn("postgresql://u:p@other:5432/y") == "postgresql://u:p@other:5432/y"


def test_host_hides_credentials() -> None:
    from ingestion.data_centers import epoch_sites

    assert epoch_sites._host("postgresql://user:secret@db.example:5433/open_navigator") == "db.example:5433/open_navigator"
