"""Tests for the jurisdiction meeting-documents API route.

Covers the in-Python grouping logic (the route fetches flat rows and groups them
without jsonb_agg, since the asyncpg pool has no JSONB codec) and confirms the
route is registered at the expected /api path.
"""

from __future__ import annotations

from datetime import date

from api.routes.jurisdiction_meeting_documents import _group_meeting_documents


def _row(doc_date, body_name, document_type, document_url, source, event_meeting_id):
    return {
        "doc_date": doc_date,
        "body_name": body_name,
        "document_type": document_type,
        "document_url": document_url,
        "source": source,
        "event_meeting_id": event_meeting_id,
    }


def test_group_two_meetings_agenda_before_minutes():
    """Two (date, body) groups, each with agenda+minutes, group correctly."""
    d1 = date(2026, 1, 15)
    d2 = date(2025, 12, 4)
    # Pre-sorted as the SQL ORDER BY would deliver: date DESC, body ASC,
    # agenda(0) before minutes(1).
    rows = [
        _row(d1, "City Council", "agenda", "http://x/a1.pdf", "suiteone", None),
        _row(d1, "City Council", "minutes", "http://x/m1.pdf", "suiteone", 8013),
        _row(d2, "Zoning Board", "agenda", "http://x/a2.pdf", "civicclerk", None),
        _row(d2, "Zoning Board", "minutes", "http://x/m2.pdf", "civicclerk", None),
    ]

    groups = _group_meeting_documents(rows)

    assert len(groups) == 2

    g1 = groups[0]
    assert g1.doc_date == d1
    assert g1.body_name == "City Council"
    # event_meeting_id is the first non-null among the group's rows.
    assert g1.event_meeting_id == 8013
    assert [d.document_type for d in g1.documents] == ["agenda", "minutes"]
    assert g1.documents[0].document_url == "http://x/a1.pdf"

    g2 = groups[1]
    assert g2.doc_date == d2
    assert g2.body_name == "Zoning Board"
    # Orphan-only group: no doc matched an analyzed meeting.
    assert g2.event_meeting_id is None
    assert [d.document_type for d in g2.documents] == ["agenda", "minutes"]

    total_docs = sum(len(g.documents) for g in groups)
    assert total_docs == 4


def test_group_empty_rows():
    assert _group_meeting_documents([]) == []


def test_route_registered_at_api_path():
    from api.main import app

    paths = {
        getattr(r, "path", None) or getattr(r, "path_format", None) for r in app.routes
    }
    assert "/api/jurisdiction/{jurisdiction_id}/meeting-documents" in paths
