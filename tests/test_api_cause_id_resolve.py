"""Unknown / NTEE cause_id must 400 on search and decisions browse (#578)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes.search import (
    CAUSE_KEYWORDS,
    require_cause_tsquery,
    resolve_cause_tsquery,
)


def test_everyorg_cause_resolves():
    q = resolve_cause_tsquery("education")
    assert q is not None
    assert "school" in q or "education" in q
    assert require_cause_tsquery("education") == q


@pytest.mark.parametrize("cause_id", ["A", "B", "ntee-A", "not-a-real-cause"])
def test_ntee_and_unknown_cause_return_none(cause_id: str):
    assert resolve_cause_tsquery(cause_id) is None
    assert cause_id.strip().lower() not in CAUSE_KEYWORDS


@pytest.mark.parametrize("cause_id", ["A", "B", "not-a-real-cause"])
def test_require_cause_tsquery_raises_400(cause_id: str):
    with pytest.raises(HTTPException) as ei:
        require_cause_tsquery(cause_id)
    assert ei.value.status_code == 400
    assert ei.value.detail == f"unknown cause_id {cause_id}"


def test_decision_browse_imports_require_cause_tsquery():
    from api.routes import decision_browse as db

    assert db.require_cause_tsquery is require_cause_tsquery
