"""
CLI: detect cross-level relations between state-bill and local-decision questions.

This is the differentiator — the link nobody else surfaces: a local council
decision and a state bill that address the same policy question, especially when
the state bill would **preempt** local authority ("your city regulated STRs;
HB 217 in Montgomery would preempt local STR ordinances entirely").

Method: compare each state-scope question centroid to every local-scope question
centroid (same embedding space). For pairs above a similarity threshold, classify
the relation from the state question's member-bill language:
  * preempts   — bills that strip/limit local authority (preempt, supersede,
                 "uniform statewide", "local government shall not", prohibit local)
  * implements — bills that authorize/enable local action
  * related    — topical overlap without a clear preempt/enable signal

Writes ``bronze.bronze_question_relation`` (from=state question, to=local
question). Only real, above-threshold pairs are written — no fabricated links.

    python -m llm.policy_questions.link_questions [--threshold 0.45]
"""

from __future__ import annotations

import argparse
from typing import Dict, List

import numpy as np
from loguru import logger

from llm.policy_questions import cluster as cl
from llm.policy_questions import db, sources

_PREEMPT_KW = (
    "preempt", "supersede", "uniform statewide", "uniform throughout the state",
    "local government shall not", "municipality shall not", "prohibit a local",
    "prohibits a local", "may not be regulated by", "exclusive jurisdiction of the state",
    "statewide standard", "shall not adopt", "shall not enforce", "void any local",
)
_IMPLEMENT_KW = (
    "authorize a", "authorize the governing", "authorize municipalit", "authorize counties",
    "authorize a local", "enable local", "permit a municipality", "allow a local",
    "grant authority to", "authorize the county",
)


def _member_text(conn, scope_source: str) -> Dict[str, str]:
    """question_id -> concatenated member-bill title/desc text (for keyword classify)."""
    out: Dict[str, List[str]] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            select qi.question_id, coalesce(b.title,'') || ' ' || coalesce(b.latest_action_description,'')
            from bronze.bronze_question_instance qi
            join gold.bills b on b.bill_uid = qi.source_id
            where qi.source_type = %s
            """,
            (sources.STATE_BILL,),
        )
        for qid, text in cur.fetchall():
            out.setdefault(qid, []).append((text or "").lower())
    return {qid: " ".join(texts) for qid, texts in out.items()}


def _classify(text: str) -> tuple[str, str]:
    for kw in _PREEMPT_KW:
        if kw in text:
            return "preempts", kw
    for kw in _IMPLEMENT_KW:
        if kw in text:
            return "implements", kw
    return "related", ""


def run(threshold: float = 0.45, database_url: str | None = None) -> Dict[str, int]:
    conn = db.connect(database_url)
    db.ensure_tables(conn)

    with conn.cursor() as cur:
        cur.execute("""
            select c.question_id, pq.scope, c.centroid, pq.canonical_text
            from bronze.bronze_question_centroid c
            join bronze.bronze_policy_question pq using (question_id)
            where c.centroid is not null
        """)
        rows = cur.fetchall()

    local = [(qid, np.asarray(v, dtype=np.float32), txt) for qid, scope, v, txt in rows if scope == "local"]
    state = [(qid, np.asarray(v, dtype=np.float32), txt) for qid, scope, v, txt in rows if scope == "state"]
    if not local or not state:
        logger.warning("Need both local and state questions to link (local={}, state={})", len(local), len(state))
        conn.close()
        return {"relations": 0}

    local_mat = np.vstack([l[1] for l in local])
    member_text = _member_text(conn, sources.STATE_BILL)

    rel_rows = []
    by_type: Dict[str, int] = {}
    for sqid, svec, stext in state:
        idx, score = cl.nearest_centroid(svec, local_mat)
        if idx < 0 or score < threshold:
            continue
        lqid, _, ltext = local[idx]
        rtype, kw = _classify(member_text.get(sqid, ""))
        evidence = f"sim={score:.2f}" + (f"; matched '{kw}'" if kw else "") + f"; state≈local: {ltext[:60]}"
        rel_rows.append((db.md5(sqid, lqid, rtype), sqid, lqid, rtype, evidence))
        by_type[rtype] = by_type.get(rtype, 0) + 1

    with conn.cursor() as cur:
        cur.execute("truncate table bronze.bronze_question_relation")
    conn.commit()
    db.upsert(conn, "bronze.bronze_question_relation",
              ["relation_id", "from_question_id", "to_question_id", "relation_type", "evidence"],
              rel_rows, conflict_key="relation_id")
    logger.success("Built {} cross-level relations: {}", len(rel_rows), by_type)
    conn.close()
    return {"relations": len(rel_rows), **by_type}


def main() -> None:
    ap = argparse.ArgumentParser(description="Link state-bill questions to local-decision questions.")
    ap.add_argument("--threshold", type=float, default=0.45)
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(threshold=args.threshold, database_url=args.database_url)


if __name__ == "__main__":
    main()
