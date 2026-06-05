"""Unit tests for the OpenStates officials bronze loader
(ingestion.openstates.officials).

Exercises the pure row-shaping / value-tuple / env-resolution logic with
fixtures; no live database required.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion.openstates import officials as oo


# ---------------------------------------------------------------------------
# state code / --state normalization
# ---------------------------------------------------------------------------
def test_state_code_from_juris_extracts_upper():
    juris = "ocd-jurisdiction/country:us/state:al/place:tuscaloosa/government"
    assert oo.state_code_from_juris(juris) == "AL"


def test_state_code_from_juris_handles_none_and_unmatched():
    assert oo.state_code_from_juris(None) is None
    assert oo.state_code_from_juris("ocd-jurisdiction/country:us/government") is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("al", "al"),
        ("AL", "al"),
        ("state:al", "al"),
        ("ocd-jurisdiction/country:us/state:al/place:x/government", "al"),
        ("/state:ny/", "ny"),
        ("", None),
        (None, None),
        ("alabama", None),
        ("usa", None),
    ],
)
def test_normalize_state_arg(raw, expected):
    assert oo.normalize_state_arg(raw) == expected


# ---------------------------------------------------------------------------
# shape_official_row
# ---------------------------------------------------------------------------
def _raw_record() -> dict:
    return {
        "ocd_membership_id": "ocd-membership/9135d097-cf2b-404f-a69b-f9300ca7b54e",
        "ocd_person_id": "ocd-person/abc",
        "full_name": "Walt Maddox",
        "party": "Democratic",
        "role": "Mayor",
        "district": None,
        "ocd_organization_id": "ocd-organization/xyz",
        "organization_name": "Tuscaloosa Government",
        "organization_classification": "government",
        "ocd_jurisdiction_id": (
            "ocd-jurisdiction/country:us/state:al/place:tuscaloosa/government"
        ),
        "email": "mayor@tuscaloosa.com",
        "image": "http://img/1.jpg",
        "start_date": "2021-11-01",
        "end_date": "",
        "source_created_at": datetime(2021, 1, 1, tzinfo=timezone.utc),
        "source_updated_at": datetime(2024, 3, 2, tzinfo=timezone.utc),
    }


def test_shape_official_row_passes_core_fields_and_derives_state():
    shaped = oo.shape_official_row(_raw_record())
    assert shaped["ocd_membership_id"].startswith("ocd-membership/9135d097")
    assert shaped["full_name"] == "Walt Maddox"
    assert shaped["role"] == "Mayor"
    assert shaped["state_code"] == "AL"
    assert shaped["organization_name"] == "Tuscaloosa Government"
    assert shaped["organization_classification"] == "government"
    assert shaped["ocd_jurisdiction_id"].endswith("place:tuscaloosa/government")
    assert shaped["email"] == "mayor@tuscaloosa.com"
    # empty-string end_date becomes None (open-ended term)
    assert shaped["end_date"] is None


def test_shape_official_row_empty_strings_become_none():
    shaped = oo.shape_official_row(
        {
            "ocd_membership_id": "ocd-membership/1",
            "full_name": "",
            "party": "",
            "district": "",
            "ocd_jurisdiction_id": None,
        }
    )
    assert shaped["full_name"] is None
    assert shaped["party"] is None
    assert shaped["district"] is None
    assert shaped["state_code"] is None


def test_shape_official_row_synthesizes_missing_membership_id():
    # No / blank membership id -> deterministic synthesized PK, never NULL.
    rec = {
        "ocd_membership_id": "",
        "ocd_person_id": "ocd-person/p1",
        "ocd_organization_id": "ocd-organization/o1",
        "role": "Council Member",
        "post_id": "ocd-post/d3",
    }
    shaped = oo.shape_official_row(rec)
    assert shaped["ocd_membership_id"].startswith("ocd-membership/synth-")
    # Deterministic: same natural key -> same id.
    assert shaped["ocd_membership_id"] == oo.shape_official_row(rec)["ocd_membership_id"]
    # A different role yields a different synthesized id.
    rec2 = {**rec, "role": "Mayor"}
    assert (
        oo.shape_official_row(rec2)["ocd_membership_id"]
        != shaped["ocd_membership_id"]
    )


# ---------------------------------------------------------------------------
# build_values_tuple
# ---------------------------------------------------------------------------
def test_build_values_tuple_order_and_length():
    shaped = oo.shape_official_row(_raw_record())
    batch_id = "00000000-0000-0000-0000-000000000001"
    vt = oo.build_values_tuple(batch_id, shaped)

    assert len(vt) == len(oo._INSERT_COLUMNS)
    assert vt[0] == batch_id
    assert vt[oo._INSERT_COLUMNS.index("ocd_membership_id")].startswith(
        "ocd-membership/9135d097"
    )
    assert vt[oo._INSERT_COLUMNS.index("full_name")] == "Walt Maddox"
    assert vt[oo._INSERT_COLUMNS.index("role")] == "Mayor"
    assert vt[oo._INSERT_COLUMNS.index("state_code")] == "AL"
    assert vt[oo._INSERT_COLUMNS.index("organization_name")] == "Tuscaloosa Government"


def test_build_values_tuple_template_placeholder_count_matches():
    assert oo._INSERT_TEMPLATE.count("%s") == len(oo._INSERT_COLUMNS)


# ---------------------------------------------------------------------------
# build_fetch_sql — current-term filter + ALL classifications (no chamber filter)
# ---------------------------------------------------------------------------
def test_build_fetch_sql_filters_current_term_only_without_state():
    sql, params = oo.build_fetch_sql(None)
    assert "rm.end_date IS NULL" in sql
    assert oo.CURRENT_TERM_CUTOFF in params
    # CRITICAL: must NOT restrict to legislative chambers.
    assert "classification IN" not in sql
    assert "'upper'" not in sql and "'lower'" not in sql
    # Only the current-term cutoff param when no state given.
    assert params == [oo.CURRENT_TERM_CUTOFF]


def test_build_fetch_sql_adds_state_filter():
    sql, params = oo.build_fetch_sql("al")
    assert "org.jurisdiction_id ILIKE" in sql
    assert "%/state:al/%" in params
    assert params[0] == oo.CURRENT_TERM_CUTOFF


# ---------------------------------------------------------------------------
# env resolution
# ---------------------------------------------------------------------------
def test_resolve_target_dsn_precedence(monkeypatch):
    for v in oo._TARGET_ENV_CHAIN:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://fallback")
    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgres://dev")
    assert oo.resolve_target_dsn() == "postgres://dev"


def test_resolve_target_dsn_none_when_unset(monkeypatch):
    for v in oo._TARGET_ENV_CHAIN:
        monkeypatch.delenv(v, raising=False)
    assert oo.resolve_target_dsn() is None


def test_resolve_source_dsn_default(monkeypatch):
    monkeypatch.delenv("OPENSTATES_DATABASE_URL", raising=False)
    assert oo.resolve_source_dsn() == oo._DEFAULT_SOURCE_DSN


# ---------------------------------------------------------------------------
# iter_source_officials — server-side named cursor row shaping
# ---------------------------------------------------------------------------
class _FakeNamedCursor:
    description = None

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.itersize = None
        self.closed = False

    def execute(self, sql, params=None):
        pass

    def __iter__(self):
        return iter(self._rows)

    def close(self):
        self.closed = True


class _FakeConn:
    def __init__(self, named_rows):
        self._named_rows = named_rows
        self.named_cursor: _FakeNamedCursor | None = None

    def cursor(self, name=None, cursor_factory=None):
        assert name is not None
        assert cursor_factory is oo.RealDictCursor
        self.named_cursor = _FakeNamedCursor(self._named_rows)
        return self.named_cursor


def test_iter_source_officials_shapes_rows_without_touching_description():
    named_rows = [
        {
            "ocd_membership_id": "ocd-membership/aaaa",
            "full_name": "Walt Maddox",
            "role": "Mayor",
            "ocd_jurisdiction_id": (
                "ocd-jurisdiction/country:us/state:al/place:tuscaloosa/government"
            ),
        },
        {
            "ocd_membership_id": "ocd-membership/bbbb",
            "full_name": "Jane Rep",
            "role": "member",
            "ocd_jurisdiction_id": "ocd-jurisdiction/country:us/state:ny/government",
        },
    ]
    conn = _FakeConn(named_rows)
    out = list(oo.iter_source_officials(conn, state=None, limit=None))

    assert [r["ocd_membership_id"] for r in out] == [
        "ocd-membership/aaaa",
        "ocd-membership/bbbb",
    ]
    assert [r["state_code"] for r in out] == ["AL", "NY"]
    assert conn.named_cursor.itersize == 2000
    assert conn.named_cursor.closed is True


def test_iter_source_officials_respects_fetch_size():
    conn = _FakeConn(named_rows=[])
    list(oo.iter_source_officials(conn, None, None, fetch_size=137))
    assert conn.named_cursor.itersize == 137
