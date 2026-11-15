"""Money-flow lenses whose table isn't in the database are unavailable, not a warning per request (#284).

Production (Neon) deliberately doesn't carry `grant` or `nonprofit_sector_revenue`.
"""

import asyncio

import asyncpg
import pytest

from api.routes import money_flow


class _MissingTableConn:
    """A connection where every query hits a missing relation, counting calls."""

    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, *_args, **_kwargs):
        self.calls += 1
        raise asyncpg.exceptions.UndefinedTableError('relation "grant" does not exist')


@pytest.fixture(autouse=True)
def _reset_not_served():
    money_flow._NOT_SERVED.clear()
    yield
    money_flow._NOT_SERVED.clear()


def test_grants_lens_is_empty_and_queried_once() -> None:
    conn = _MissingTableConn()
    first = asyncio.run(money_flow._grants(conn, state_code=None))
    second = asyncio.run(money_flow._grants(conn, state_code="AL"))
    assert first.placeholder and second.placeholder
    assert first.links == [] and first.head_amount == "—"
    assert conn.calls == 1
    assert "grant" in money_flow._NOT_SERVED


def test_economy_lens_is_empty_and_queried_once() -> None:
    conn = _MissingTableConn()
    for _ in range(2):
        lens = asyncio.run(money_flow._economy(conn, state_code="AL", city=None, scope_label="Alabama"))
        assert lens.placeholder and lens.links == []
    assert conn.calls == 1
    assert "nonprofit_sector_revenue" in money_flow._NOT_SERVED


def test_other_errors_are_not_cached() -> None:
    class _Flaky:
        calls = 0

        async def fetch(self, *_a, **_k):
            _Flaky.calls += 1
            raise ConnectionError("network blip")

    conn = _Flaky()
    for _ in range(2):
        assert asyncio.run(money_flow._grants(conn, state_code=None)).placeholder
    assert _Flaky.calls == 2
    assert money_flow._NOT_SERVED == set()
