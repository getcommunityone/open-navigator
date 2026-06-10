"""
Source readers for instance types feeding the policy-question registry.

Phase 1 = local decisions (``public.event_decision``). Phase 2 will add
``state_bill`` here behind the same row shape so the rest of the pipeline is
source-agnostic.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

LOCAL_DECISION = "local_decision"
STATE_BILL = "state_bill"

_DECISION_SQL = """
select
    event_decision_id,
    headline,
    decision_statement,
    primary_theme,
    competing_views,
    state_code,
    jurisdiction_name,
    city,
    outcome,
    extracted_at
from public.event_decision
"""


def _as_obj(v: Any) -> Optional[Any]:
    """JSONB may arrive as dict (psycopg2 default) or TEXT; tolerate both."""
    if v is None or isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return None
    return None


def load_decisions(conn) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(_DECISION_SQL)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        r["competing_views"] = _as_obj(r["competing_views"])
        r["source_type"] = LOCAL_DECISION
        r["source_id"] = r["event_decision_id"]
    return rows


def embed_text_for(row: Dict[str, Any]) -> str:
    """Text used to embed a decision: statement + dominant problem diagnosis."""
    parts: List[str] = []
    stmt = row.get("decision_statement") or row.get("headline") or ""
    if stmt:
        parts.append(str(stmt).strip())
    cv = row.get("competing_views")
    if isinstance(cv, dict):
        dom = cv.get("dominant_view")
        if isinstance(dom, dict):
            pd = dom.get("problem_diagnosis")
            if isinstance(pd, str) and pd.strip():
                parts.append(pd.strip())
    return "\n".join(parts)[:2000]
