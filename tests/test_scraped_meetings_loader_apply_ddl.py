"""--apply-ddl must find its migration and must not drop populated scraped-meetings tables unasked (#403)."""
from __future__ import annotations

from typing import Any, Self

import pytest

from scripts.discovery import load_scraped_meetings_manifests_to_bronze as loader

_TABLES = list(loader.TABLE_FOR_PREFIX.values())


class _Cursor:
    """Answers the existence and count queries from a {table: rows or None (missing)} map; records the rest."""

    def __init__(self, tables: dict[str, int | None], executed: list[str]) -> None:
        self._tables = tables
        self._executed = executed
        self._answer: Any = None

    def execute(self, sql: str, params: Any = None) -> None:
        if "to_regclass" in sql:
            self._answer = (self._tables[params[0]] is not None,)
        elif sql.startswith("SELECT count(*) FROM "):
            self._answer = (self._tables[sql.removeprefix("SELECT count(*) FROM ").strip()],)
        else:
            self._executed.append(sql)

    def fetchone(self) -> Any:
        return self._answer

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Conn:
    def __init__(self, tables: dict[str, int | None]) -> None:
        self.tables = tables
        self.executed: list[str] = []
        self.commits = 0

    def cursor(self) -> _Cursor:
        return _Cursor(self.tables, self.executed)

    def commit(self) -> None:
        self.commits += 1


def test_the_migration_is_where_the_loader_looks_for_it():
    assert loader.MIGRATION_PATH.is_file()
    assert "DROP TABLE IF EXISTS" in loader.MIGRATION_PATH.read_text(encoding="utf-8")


def test_refuses_when_a_table_has_rows_and_runs_nothing(capsys: pytest.CaptureFixture[str]):
    conn = _Conn({_TABLES[0]: 0, _TABLES[1]: 1234, _TABLES[2]: None})
    with pytest.raises(SystemExit) as exc:
        loader._apply_ddl(conn)
    message = str(exc.value)
    assert _TABLES[1] in message and "1,234 rows" in message and "--drop-existing" in message
    assert _TABLES[0] not in message and _TABLES[2] not in message
    assert conn.executed == [] and conn.commits == 0


def test_runs_the_migration_when_every_table_is_empty_or_missing():
    conn = _Conn({_TABLES[0]: 0, _TABLES[1]: None, _TABLES[2]: 0})
    loader._apply_ddl(conn)
    assert len(conn.executed) == 1 and "CREATE TABLE" in conn.executed[0]
    assert conn.commits == 1


def test_drop_existing_runs_the_migration_over_populated_tables():
    conn = _Conn({_TABLES[0]: 5, _TABLES[1]: 7, _TABLES[2]: 9})
    loader._apply_ddl(conn, drop_existing=True)
    assert len(conn.executed) == 1 and conn.commits == 1


def test_drop_existing_without_apply_ddl_is_a_usage_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sys.argv", ["loader", "-s", "AL", "--drop-existing"])
    with pytest.raises(SystemExit) as exc:
        loader.main()
    assert exc.value.code == 2
