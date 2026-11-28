"""Trending terms and hot words (#1399): the API shapes, and the marts against the warehouse (counts, privacy filter,
boilerplate)."""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import trending_terms as tt

TID = "0123456789abcdef0123456789abcdef"


class _Conn:
    def __init__(self, rows: list[dict[str, Any]], head: dict[str, Any] | None = None):
        self.rows = rows
        self.head = head
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.head


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def _get(monkeypatch, pool_factory, path: str, params: dict | None = None) -> httpx.Response:
    monkeypatch.setattr(tt, "get_db_pool", pool_factory)
    app = FastAPI()
    app.include_router(tt.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def _term_row(**kw: Any) -> dict[str, Any]:
    # Test-only row: nothing here is served by the app.
    row = dict(term_key=TID, term="sample term", rank=1, meetings_a=10, meetings_b=40, recorded_a=1000,
               recorded_b=2000, share_a=0.01, share_b=0.02, rise=2.0, n_meetings=50, n_jurisdictions=12,
               hot_score=None, is_sensitive=False, latest_meeting_date=date(2026, 11, 1), year_a=2025, year_b=2026)
    row.update(kw)
    return row


def test_terms_sql_uses_a_fixed_rank_column_and_scope() -> None:
    for sort, col in tt.RANK_COLUMN.items():
        sql, p = tt.terms_sql(tt.TrendScope(level="national"), sort, 10)  # type: ignore[arg-type]
        assert f"ORDER BY {col}" in sql and f"{col} IS NOT NULL" in sql and "is_served" in sql
        assert p == ["US", 10]
    _, p = tt.terms_sql(tt.TrendScope(level="state", state_code="GA"), "hot", 5)
    assert p == ["GA", 5]


def test_terms_route_years_as_strings(monkeypatch) -> None:
    conn = _Conn([_term_row()])

    async def pool():
        return _Pool(conn)

    r = _get(monkeypatch, pool, "/api/trends/terms", {"state": "georgia", "sort": "rising"})
    assert r.status_code == 200
    body = r.json()
    assert body["year_a"] == "2025" and body["year_b"] == "2026"
    assert body["scope"] == {"level": "state", "state_code": "GA", "state": "Georgia", "requested_city": None}
    assert body["terms"][0]["term_id"] == TID and body["terms"][0]["latest_meeting_date"] == "2026-11-01"
    assert conn.calls[0][1][0] == "GA"


def test_city_is_answered_by_its_state(monkeypatch) -> None:
    async def pool():
        return _Pool(_Conn([]))

    body = _get(monkeypatch, pool, "/api/trends/terms", {"state": "AL", "city": "Tuscaloosa"}).json()
    assert body["scope"]["level"] == "state" and body["scope"]["requested_city"] == "Tuscaloosa"
    assert body["terms"] == [] and body["year_a"] is None


def test_bad_sort_is_422_and_db_failure_is_503(monkeypatch) -> None:
    async def ok():
        return _Pool(_Conn([]))

    assert _get(monkeypatch, ok, "/api/trends/terms", {"sort": "loud"}).status_code == 422

    async def down():
        raise RuntimeError("down")

    assert _get(monkeypatch, down, "/api/trends/terms").status_code == 503


def test_evidence_never_names_a_speaker_for_a_sensitive_term(monkeypatch) -> None:
    ev = dict(video_id="v1", meeting_title="Council", meeting_date=date(2026, 10, 1), jurisdiction_name="Somewhere",
              state_code="GA", video_url=None, excerpt="… the <mark>term</mark> …", excerpt_source="public_comment",
              start_seconds=12.0, speaker_display_name="Jane D.", total=1)
    conn = _Conn([ev], head={"term": "sample", "is_sensitive": True, "n_meetings": 7})

    async def pool():
        return _Pool(conn)

    body = _get(monkeypatch, pool, f"/api/trends/terms/{TID}/evidence", {"state": "GA"}).json()
    assert body["is_sensitive"] is True and body["total_meetings"] == 7 and body["total"] == 1
    assert body["items"][0]["speaker_display_name"] is None
    assert "<mark>term</mark>" in body["items"][0]["excerpt"]
    sql, params = conn.calls[-1]
    assert "e.state_code = $2" in sql and params[:2] == (TID, "GA")


def test_evidence_rejects_a_malformed_id(monkeypatch) -> None:
    async def pool():
        return _Pool(_Conn([], head=None))

    assert _get(monkeypatch, pool, "/api/trends/terms/not-a-key/evidence").status_code == 404
    assert _get(monkeypatch, pool, f"/api/trends/terms/{TID}/evidence").status_code == 404


# --- the live warehouse ---------------------------------------------------------------------------------------------

_DB = {
    "host": os.environ.get("TOPIC_TEST_DB_HOST", "localhost"),
    "port": int(os.environ.get("TOPIC_TEST_DB_PORT", "5433")),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
    "database": "open_navigator",
}


def _live(query):
    """Run ``query(conn)`` on the local warehouse; skip when it (or the trending marts) isn't there."""

    async def run():
        try:
            conn = await asyncpg.connect(**_DB, timeout=3)
        except (TimeoutError, OSError, asyncpg.PostgresError):
            return None
        try:
            await conn.execute("SET statement_timeout = '120s'")
            return await query(conn)
        except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.InvalidSchemaNameError):
            return None
        finally:
            await conn.close()

    out = asyncio.run(run())
    if out is None:
        pytest.skip("local warehouse or trending marts not available")
    return out


def test_meeting_base_matches_recorded_meeting_year() -> None:
    async def q(c):
        mine = await c.fetch(
            "SELECT meeting_year, count(*)::int AS n FROM intermediate.int_trending_term__meeting GROUP BY 1 ORDER BY 1")
        rec = await c.fetch(
            "SELECT meeting_year, sum(recorded_meetings)::int AS n FROM gold.recorded_meeting_year "
            "WHERE meeting_year IN (SELECT DISTINCT meeting_year FROM intermediate.int_trending_term__meeting) "
            "GROUP BY 1 ORDER BY 1")
        return [tuple(r) for r in mine], [tuple(r) for r in rec]

    mine, rec = _live(q)
    assert mine and mine == rec


def test_mart_counts_match_a_direct_recount() -> None:
    """recorded_* = counted meetings, and a served term's meetings = a direct full-text recount over transcripts."""

    async def q(c):
        row = await c.fetchrow(
            "SELECT term_key, term_tsquery, meetings_a, meetings_b, recorded_a, recorded_b, year_a, year_b "
            "FROM gold.trending_term WHERE scope_code = 'US' AND is_served AND rank_rising IS NOT NULL "
            "ORDER BY meetings_b LIMIT 1")
        if row is None:
            return None
        rec = await c.fetchrow(
            "SELECT count(*) FILTER (WHERE meeting_year = $1)::int AS a, count(*) FILTER (WHERE meeting_year = $2)::int AS b "
            "FROM intermediate.int_trending_term__meeting WHERE counted", row["year_a"], row["year_b"])
        hits = await c.fetchrow(
            "SELECT count(*) FILTER (WHERE m.meeting_year = $2)::int AS a, count(*) FILTER (WHERE m.meeting_year = $3)::int AS b "
            "FROM intermediate.int_trending_term__meeting m WHERE m.counted AND EXISTS ("
            "  SELECT 1 FROM gold.event_documents d WHERE d.video_id = m.video_id AND d.document_type = 'transcript' "
            "  AND d.content_tsv @@ $1::tsquery AND d.event_document_id = ("
            "    SELECT d2.event_document_id FROM gold.event_documents d2 WHERE d2.video_id = m.video_id "
            "    AND d2.document_type = 'transcript' AND d2.content_tsv IS NOT NULL "
            "    ORDER BY d2.content_length DESC NULLS LAST LIMIT 1))",
            row["term_tsquery"], row["year_a"], row["year_b"])
        return row, rec, hits

    row, rec, hits = _live(q)
    assert (row["recorded_a"], row["recorded_b"]) == (rec["a"], rec["b"])
    assert (row["meetings_a"], row["meetings_b"]) == (hits["a"], hits["b"])


def test_privacy_filter_drops_private_first_names() -> None:
    async def q(c):
        cand = {r["term"]: r["drop_reason"] for r in await c.fetch(
            "SELECT term, drop_reason FROM intermediate.int_trending_term__candidate "
            "WHERE term IN ('john', 'sarah', 'michael', 'jennifer')")}
        served = await c.fetch(
            "SELECT DISTINCT t.term FROM gold.trending_term t "
            "JOIN intermediate.int_trending_term__name_lexicon l ON l.word = t.term "
            "WHERE t.is_served AND t.n_words = 1 AND t.name_allowed_as IS NULL AND l.n_given >= 20 "
            "AND t.term NOT IN (SELECT term FROM seeds.trending_term_common_word)")
        return cand, [r["term"] for r in served]

    cand, served_names = _live(q)
    # A sample private first name heard in many meetings is a candidate, and the filter drops it.
    assert cand.get("john") == "person_name"
    assert all(cand.get(n) in (None, "person_name", "thin_sample") for n in ("sarah", "michael", "jennifer"))
    # No served single word is a common given name, unless it is a reviewed public figure / official or a reviewed
    # common civic word that is also a name (trending_term_common_word: "bill", "april").
    assert served_names == []


def test_boilerplate_is_excluded_from_served_terms() -> None:
    async def q(c):
        bad_phrase = await c.fetch(
            "SELECT t.term FROM gold.trending_term t JOIN seeds.trending_term_excluded e ON e.match = 'phrase' "
            "AND (' ' || t.term || ' ') LIKE ('% ' || e.term || ' %') WHERE t.is_served")
        bad_edge = await c.fetch(
            "SELECT t.term FROM gold.trending_term t JOIN seeds.trending_term_excluded e ON e.match = 'word' "
            "AND e.term IN (split_part(t.term, ' ', 1), split_part(t.term, ' ', t.n_words)) WHERE t.is_served")
        samples = await c.fetch(
            "SELECT term FROM gold.trending_term WHERE term IN "
            "('motion to approve', 'public hearing', 'second', 'roll call', 'next item', 'thank you', 'um')")
        return bad_phrase, bad_edge, samples

    bad_phrase, bad_edge, samples = _live(q)
    assert bad_phrase == [] and bad_edge == [] and samples == []


def test_sensitive_terms_never_carry_a_speaker_and_minimums_hold() -> None:
    async def q(c):
        named = await c.fetchval(
            "SELECT count(*) FROM gold.trending_term_evidence e JOIN intermediate.int_trending_term__candidate c "
            "ON c.term_key = e.term_key WHERE c.is_sensitive AND e.speaker_display_name IS NOT NULL")
        thin = await c.fetchval(
            "SELECT count(*) FROM gold.trending_term WHERE scope_code = 'US' AND eligible "
            "AND (meetings_b < 15 OR n_jurisdictions < 5)")
        served_mb = await c.fetchval(
            "SELECT coalesce(sum(pg_column_size(t.*)), 0)::numeric / 1e6 FROM gold.trending_term t WHERE t.is_served")
        return named, thin, served_mb

    named, thin, served_mb = _live(q)
    assert named == 0 and thin == 0
    assert served_mb <= 3
