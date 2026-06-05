"""Unit tests for the OpenStates bills bronze loader (ingestion.openstates.bills).

Exercises the pure row-shaping / value-tuple / env-resolution logic with fixtures;
no live database required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from ingestion.openstates import bills as ob


# ---------------------------------------------------------------------------
# state code / --state normalization
# ---------------------------------------------------------------------------
def test_state_code_from_juris_extracts_upper():
    juris = "ocd-jurisdiction/country:us/state:al/government"
    assert ob.state_code_from_juris(juris) == "AL"


def test_state_code_from_juris_handles_none_and_unmatched():
    assert ob.state_code_from_juris(None) is None
    assert ob.state_code_from_juris("ocd-jurisdiction/country:us/government") is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("al", "al"),
        ("AL", "al"),
        ("state:al", "al"),
        ("ocd-jurisdiction/country:us/state:al/government", "al"),
        ("/state:ny/", "ny"),
        ("", None),
        (None, None),
        ("alabama", None),
        ("usa", None),
    ],
)
def test_normalize_state_arg(raw, expected):
    assert ob.normalize_state_arg(raw) == expected


# ---------------------------------------------------------------------------
# shape_bill_row
# ---------------------------------------------------------------------------
def _raw_record() -> dict:
    return {
        "ocd_bill_id": "ocd-bill/1111",
        "identifier": "HB 1",
        "title": "An Act Concerning Things",
        "classification": ["bill"],
        "subject": ["Health", "Budget"],
        "from_organization_id": "ocd-organization/lower",
        "legislative_session_id": "sess-uuid",
        "session_identifier": "2023rs",
        "session_name": "2023 Regular Session",
        "ocd_jurisdiction_id": "ocd-jurisdiction/country:us/state:al/government",
        "first_action_date": "2023-01-10",
        "latest_action_date": "2023-03-01",
        "latest_action_description": "Signed by Governor",
        "latest_passage_date": "2023-02-28",
        "citations": [{"url": "http://x"}],
        "extras": {"foo": "bar"},
        "sponsorships": [
            {
                "id": "sp-1",
                "name": "Jane Rep",
                "entity_type": "person",
                "primary": True,
                "classification": "primary",
                "person_id": "ocd-person/abc",
                "organization_id": None,
            }
        ],
        "abstracts": [{"abstract": "summary", "note": "official"}],
        "titles": [{"title": "Short Title", "note": "short"}],
        "identifiers": [{"identifier": "HB1-alt"}],
        "source_created_at": datetime(2023, 1, 1, tzinfo=timezone.utc),
        "source_updated_at": datetime(2023, 3, 2, tzinfo=timezone.utc),
    }


def test_shape_bill_row_passes_core_fields_and_derives_state():
    shaped = ob.shape_bill_row(_raw_record())
    assert shaped["ocd_bill_id"] == "ocd-bill/1111"
    assert shaped["identifier"] == "HB 1"
    assert shaped["state_code"] == "AL"
    assert shaped["ocd_jurisdiction_id"].endswith("state:al/government")
    assert shaped["session_identifier"] == "2023rs"
    assert shaped["classification"] == ["bill"]
    assert shaped["subject"] == ["Health", "Budget"]
    assert len(shaped["sponsorships"]) == 1
    assert shaped["sponsorships"][0]["person_id"] == "ocd-person/abc"
    assert shaped["abstracts"][0]["note"] == "official"


def test_shape_bill_row_defaults_missing_collections():
    minimal = {
        "ocd_bill_id": "ocd-bill/2222",
        "ocd_jurisdiction_id": None,
    }
    shaped = ob.shape_bill_row(minimal)
    assert shaped["ocd_bill_id"] == "ocd-bill/2222"
    assert shaped["state_code"] is None
    assert shaped["classification"] == []
    assert shaped["subject"] == []
    assert shaped["citations"] == []
    assert shaped["extras"] == {}
    assert shaped["sponsorships"] == []
    assert shaped["abstracts"] == []
    assert shaped["titles"] == []
    assert shaped["identifiers"] == []
    assert shaped["identifier"] is None
    assert shaped["title"] is None


def test_shape_bill_row_empty_strings_become_none():
    shaped = ob.shape_bill_row(
        {"ocd_bill_id": "ocd-bill/3", "identifier": "", "title": "", "session_name": ""}
    )
    assert shaped["identifier"] is None
    assert shaped["title"] is None
    assert shaped["session_name"] is None


# ---------------------------------------------------------------------------
# build_values_tuple
# ---------------------------------------------------------------------------
def test_build_values_tuple_order_and_jsonb_serialization():
    shaped = ob.shape_bill_row(_raw_record())
    batch_id = "00000000-0000-0000-0000-000000000001"
    vt = ob.build_values_tuple(batch_id, shaped)

    # Length must match the INSERT column list exactly.
    assert len(vt) == len(ob._INSERT_COLUMNS)

    # Positional spot-checks against column order.
    assert vt[0] == batch_id
    assert vt[ob._INSERT_COLUMNS.index("ocd_bill_id")] == "ocd-bill/1111"
    assert vt[ob._INSERT_COLUMNS.index("identifier")] == "HB 1"
    assert vt[ob._INSERT_COLUMNS.index("state_code")] == "AL"

    # JSONB columns are serialized to JSON text.
    classification = vt[ob._INSERT_COLUMNS.index("classification")]
    assert json.loads(classification) == ["bill"]
    sponsorships = vt[ob._INSERT_COLUMNS.index("sponsorships")]
    assert json.loads(sponsorships)[0]["name"] == "Jane Rep"
    extras = vt[ob._INSERT_COLUMNS.index("extras")]
    assert json.loads(extras) == {"foo": "bar"}


def test_build_values_tuple_template_placeholder_count_matches():
    # The execute_values template must have one placeholder per column.
    assert ob._INSERT_TEMPLATE.count("%s") == len(ob._INSERT_COLUMNS)


def test_build_values_tuple_serializes_unknown_types():
    # default=str must keep json.dumps from choking on datetimes nested in extras.
    shaped = ob.shape_bill_row(
        {"ocd_bill_id": "x", "extras": {"ts": datetime(2024, 1, 1)}}
    )
    vt = ob.build_values_tuple("b", shaped)
    extras = vt[ob._INSERT_COLUMNS.index("extras")]
    assert "2024-01-01" in json.loads(extras)["ts"]


# ---------------------------------------------------------------------------
# env resolution
# ---------------------------------------------------------------------------
def test_resolve_target_dsn_precedence(monkeypatch):
    for v in ob._TARGET_ENV_CHAIN:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://fallback")
    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgres://dev")
    # Highest-precedence wins.
    assert ob.resolve_target_dsn() == "postgres://dev"


def test_resolve_target_dsn_falls_through(monkeypatch):
    for v in ob._TARGET_ENV_CHAIN:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("OPEN_NAVIGATOR_DATABASE_URL", "postgres://on")
    assert ob.resolve_target_dsn() == "postgres://on"


def test_resolve_target_dsn_none_when_unset(monkeypatch):
    for v in ob._TARGET_ENV_CHAIN:
        monkeypatch.delenv(v, raising=False)
    assert ob.resolve_target_dsn() is None


def test_resolve_source_dsn_default(monkeypatch):
    monkeypatch.delenv("OPENSTATES_DATABASE_URL", raising=False)
    assert ob.resolve_source_dsn() == ob._DEFAULT_SOURCE_DSN


# ---------------------------------------------------------------------------
# child-table aggregation subquery construction (graceful degradation)
# ---------------------------------------------------------------------------
def test_child_agg_subquery_builds_when_columns_present():
    sql = ob._child_agg_subquery(
        {"abstract", "note", "bill_id"}, "opencivicdata_billabstract", ["abstract", "note"]
    )
    assert "jsonb_agg" in sql
    assert "'abstract', c.abstract" in sql
    assert "AS abstracts" in sql


def test_child_agg_subquery_empty_when_table_absent():
    sql = ob._child_agg_subquery(set(), "opencivicdata_billtitle", ["title", "note"])
    assert sql.strip().startswith("'[]'::jsonb")
    assert "AS titles" in sql
    assert "jsonb_agg" not in sql


def test_child_agg_subquery_uses_only_present_columns():
    # Only 'identifier' exists; subquery should not reference a missing column.
    sql = ob._child_agg_subquery(
        {"identifier", "bill_id"}, "opencivicdata_billidentifier", ["identifier"]
    )
    assert "'identifier', c.identifier" in sql
    assert "AS identifiers" in sql


# ---------------------------------------------------------------------------
# iter_source_bills — server-side named cursor row shaping (no cur.description)
# ---------------------------------------------------------------------------
class _FakeColumnsCursor:
    """Stand-in for the plain cursor used by _table_columns()."""

    def __init__(self, columns_by_table: dict[str, set[str]]):
        self._columns_by_table = columns_by_table
        self._rows: list[tuple[str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        # _table_columns passes the table name as the single positional param.
        table = params[0] if params else None
        self._rows = [(c,) for c in self._columns_by_table.get(table, set())]

    def fetchall(self):
        return self._rows


class _FakeNamedCursor:
    """
    Models a psycopg2 server-side *named* RealDictCursor: yields dict rows and
    leaves ``description`` as None (the regression we are guarding against —
    reading cur.description here used to raise TypeError).
    """

    description = None  # never populated for a server-side cursor pre-fetch

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.itersize = None
        self.closed = False

    def execute(self, sql, params=None):
        # No-op: the real cursor wouldn't run server-side until first fetch.
        pass

    def __iter__(self):
        return iter(self._rows)

    def close(self):
        self.closed = True


class _FakeConn:
    def __init__(self, columns_by_table, named_rows):
        self._columns_by_table = columns_by_table
        self._named_rows = named_rows
        self.named_cursor: _FakeNamedCursor | None = None

    def cursor(self, name=None, cursor_factory=None):
        if name is not None:
            # The streaming path must request a dict-style cursor factory so it
            # never depends on cur.description.
            assert cursor_factory is ob.RealDictCursor
            self.named_cursor = _FakeNamedCursor(self._named_rows)
            return self.named_cursor
        return _FakeColumnsCursor(self._columns_by_table)


def test_iter_source_bills_shapes_rows_without_touching_description():
    # All three child tables present so build_fetch_sql runs its full path.
    cols = {"bill_id", "abstract", "note", "title", "identifier"}
    columns_by_table = {
        "opencivicdata_billabstract": cols,
        "opencivicdata_billtitle": cols,
        "opencivicdata_billidentifier": cols,
    }
    named_rows = [
        {
            "ocd_bill_id": "ocd-bill/aaaa",
            "identifier": "HB 1",
            "title": "An Act",
            "ocd_jurisdiction_id": "ocd-jurisdiction/country:us/state:al/government",
            "sponsorships": [],
            "abstracts": [],
            "titles": [],
            "identifiers": [],
        },
        {
            "ocd_bill_id": "ocd-bill/bbbb",
            "identifier": "SB 2",
            "title": "Another Act",
            "ocd_jurisdiction_id": "ocd-jurisdiction/country:us/state:ny/government",
            "sponsorships": [],
            "abstracts": [],
            "titles": [],
            "identifiers": [],
        },
    ]
    conn = _FakeConn(columns_by_table, named_rows)

    out = list(ob.iter_source_bills(conn, state=None, session=None, limit=None))

    assert [r["ocd_bill_id"] for r in out] == ["ocd-bill/aaaa", "ocd-bill/bbbb"]
    # state_code derived by shape_bill_row from the jurisdiction id.
    assert [r["state_code"] for r in out] == ["AL", "NY"]
    # itersize (streaming batch knob) was set, and the cursor was closed.
    assert conn.named_cursor.itersize == 2000
    assert conn.named_cursor.closed is True


def test_iter_source_bills_respects_fetch_size():
    conn = _FakeConn(
        {
            "opencivicdata_billabstract": set(),
            "opencivicdata_billtitle": set(),
            "opencivicdata_billidentifier": set(),
        },
        named_rows=[],
    )
    list(ob.iter_source_bills(conn, None, None, None, fetch_size=137))
    assert conn.named_cursor.itersize == 137
