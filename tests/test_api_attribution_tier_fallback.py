"""A served schema without meeting_passage_speaker.attribution_tier must not 500 (#1389)."""

from __future__ import annotations

import asyncio

import asyncpg

from api.attribution_tier import TIER_FILTER, fetch_tier_aware, fetchrow_tier_aware, without_tier_filter

SQL = f"SELECT 1 FROM meeting_passage_speaker s WHERE s.speaker_display_name IS NOT NULL {TIER_FILTER}"


class _OldSchemaConn:
    """Rejects any query that names attribution_tier, like a copy published before the column existed."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def _run(self, sql: str) -> list[dict]:
        self.queries.append(sql)
        if "attribution_tier" in sql:
            raise asyncpg.exceptions.UndefinedColumnError('column s.attribution_tier does not exist')
        return [{"ok": 1}]

    async def fetch(self, sql: str, *args):
        return await self._run(sql)

    async def fetchrow(self, sql: str, *args):
        return (await self._run(sql))[0]


def test_without_tier_filter_drops_only_the_clause() -> None:
    assert "attribution_tier" not in without_tier_filter(SQL)
    assert "speaker_display_name IS NOT NULL" in without_tier_filter(SQL)


def test_fetch_retries_without_the_filter() -> None:
    conn = _OldSchemaConn()
    assert asyncio.run(fetch_tier_aware(conn, SQL, what="test")) == [{"ok": 1}]
    assert len(conn.queries) == 2


def test_fetchrow_retries_without_the_filter() -> None:
    conn = _OldSchemaConn()
    assert asyncio.run(fetchrow_tier_aware(conn, SQL, what="test")) == {"ok": 1}


def test_other_column_errors_still_raise() -> None:
    class Conn:
        async def fetch(self, sql, *a):
            raise asyncpg.exceptions.UndefinedColumnError("column s.other does not exist")

    try:
        asyncio.run(fetch_tier_aware(Conn(), SQL))
    except asyncpg.exceptions.UndefinedColumnError:
        return
    raise AssertionError("expected the error to propagate")
