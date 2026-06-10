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


# --- state bills (Phase 2) -------------------------------------------------

# gold.bills joined to bronze abstracts (only ~40% of bills carry an abstract).
_BILLS_SQL = """
select
    b.bill_uid,
    b.identifier,
    b.title,
    b.subject,
    b.state_code,
    b.session_identifier,
    b.latest_action_date,
    b.latest_action_description,
    br.abstracts
from gold.bills b
left join bronze.bronze_bills_openstates br on br.ocd_bill_id = b.ocd_bill_id
where b.state_code = %s
"""


def _subject_text(subject: Any) -> str:
    subject = _as_obj(subject)
    if isinstance(subject, list):
        return " ".join(str(s) for s in subject if s)
    return ""


def _abstract_text(abstracts: Any) -> str:
    abstracts = _as_obj(abstracts)
    if isinstance(abstracts, list):
        out = []
        for a in abstracts:
            if isinstance(a, dict) and a.get("abstract"):
                out.append(str(a["abstract"]))
            elif isinstance(a, str):
                out.append(a)
        return " ".join(out)
    return ""


def load_bills(conn, state_code: str = "AL") -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(_BILLS_SQL, (state_code,))
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    out = []
    for r in rows:
        r["source_type"] = STATE_BILL
        r["source_id"] = r["bill_uid"]
        r["subject_text"] = _subject_text(r.get("subject"))
        r["abstract_text"] = _abstract_text(r.get("abstracts"))
        r["jurisdiction_name"] = r.get("state_code")  # state-grain
        out.append(r)
    return out


def embed_text_for_bill(row: Dict[str, Any]) -> str:
    """Text used to embed a bill: title + abstract + subject tags."""
    parts: List[str] = []
    if row.get("title"):
        parts.append(str(row["title"]).strip())
    if row.get("abstract_text"):
        parts.append(row["abstract_text"].strip())
    if row.get("subject_text"):
        parts.append(row["subject_text"].strip())
    return "\n".join(parts)[:2000]


def shingle_text_for_bill(row: Dict[str, Any]) -> str:
    """Text for MinHash near-duplicate detection (literal model-bill copies)."""
    return f"{row.get('title') or ''} {row.get('abstract_text') or ''}".lower().strip()
