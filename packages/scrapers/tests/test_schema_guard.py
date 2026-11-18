"""Loaders run no DDL when their columns already exist (#534)."""

from __future__ import annotations

from typing import Any

from scrapers.youtube import bronze_transcript_tracking as btt
from scrapers.youtube.channel_about_links import ensure_bronze_events_channels_link_columns
from scrapers.youtube.schema_guard import is_base_table, missing_columns


class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn
        self._rows: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.conn.statements.append(sql)
        text = " ".join(sql.split()).lower()
        if "from information_schema.columns" in text:
            schema, table, wanted = params
            have = self.conn.columns.get(f"{schema}.{table}", set())
            self._rows = [(c,) for c in wanted if c in have]
        elif "from pg_indexes" in text:
            self._rows = [(1,)] if params[1] in self.conn.indexes else []
        elif "from pg_class" in text:
            kind = self.conn.relkinds.get(params[0])
            self._rows = [(kind,)] if kind else []
        else:
            self._rows = []

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def close(self) -> None:
        pass


class FakeConn:
    def __init__(self, columns: dict[str, set[str]], indexes: set[str] = frozenset(), relkinds=None) -> None:
        self.columns = columns
        self.indexes = set(indexes)
        self.relkinds = relkinds or {}
        self.statements: list[str] = []
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass

    def ddl(self) -> list[str]:
        return [s for s in self.statements if "alter table" in s.lower() or "create index" in s.lower()]


def test_missing_columns_reports_only_absent() -> None:
    conn = FakeConn({"bronze.t": {"a", "b"}})
    assert missing_columns(conn, "bronze", "t", ["a", "c"]) == ["c"]


def test_transcript_columns_present_runs_no_ddl() -> None:
    conn = FakeConn(
        {"bronze.bronze_event_youtube": set(btt._TRANSCRIPT_COLUMNS)},
        indexes={btt._TRANSCRIPT_INDEX},
    )
    btt.ensure_bronze_youtube_transcript_columns(conn)
    assert conn.ddl() == []
    assert conn.commits == 1


def test_transcript_column_missing_runs_ddl_under_lock_timeout() -> None:
    conn = FakeConn({"bronze.bronze_event_youtube": set(btt._TRANSCRIPT_COLUMNS[:-1])})
    btt.ensure_bronze_youtube_transcript_columns(conn)
    joined = "\n".join(conn.statements)
    assert "lock_timeout" in joined
    assert any("ALTER TABLE bronze.bronze_event_youtube" in s for s in conn.statements)


def test_channel_link_columns_present_runs_no_ddl() -> None:
    conn = FakeConn(
        {
            "bronze.bronze_events_channels": {
                "channel_external_links",
                "channel_external_links_fetched_at",
                "channel_description",
                "view_count",
            }
        }
    )
    ensure_bronze_events_channels_link_columns(conn)
    assert conn.ddl() == []


def test_is_base_table_false_for_view() -> None:
    conn = FakeConn({}, relkinds={"event": "v", "bronze.t": "r"})
    assert not is_base_table(conn, "event")
    assert is_base_table(conn, "bronze.t")
    assert not is_base_table(conn, "missing")
