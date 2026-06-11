"""
CLI: assign NEW/unmapped instances to existing questions (incremental, LLM-free).

The common steady-state path: embed new decisions (``embed_instances``), then
attach each to the nearest stored question centroid *within its coarse theme*. No
re-clustering, no Gemini calls. Below-threshold decisions are left unmapped (they
become questions on the next full re-cluster) rather than forced into a wrong one.

    python -m llm.policy_questions.assign_instances [--threshold 0.55]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Dict, List

import numpy as np
from loguru import logger

from llm.policy_questions import cluster as cl
from llm.policy_questions import db, sources


def run(threshold: float = 0.55, database_url: str | None = None) -> Dict[str, int]:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    decisions = {r["source_id"]: r for r in sources.load_decisions(conn)}

    with conn.cursor() as cur:
        cur.execute("select question_id, coarse_theme, centroid from bronze.bronze_question_centroid")
        centroids = cur.fetchall()
        cur.execute("select source_id from bronze.bronze_question_instance where source_type=%s",
                    (sources.LOCAL_DECISION,))
        mapped = {r[0] for r in cur.fetchall()}
        cur.execute(
            "select source_id, coarse_theme, embedding from bronze.bronze_pq_embedding "
            "where source_type=%s and embedding is not null", (sources.LOCAL_DECISION,),
        )
        embs = cur.fetchall()

    by_theme: Dict[str, List] = defaultdict(list)
    qid_by_theme: Dict[str, List[str]] = defaultdict(list)
    for qid, theme, vec in centroids:
        by_theme[theme].append(np.asarray(vec, dtype=np.float32))
        qid_by_theme[theme].append(qid)
    theme_mat = {t: np.vstack(v) for t, v in by_theme.items()}

    rows = []
    skipped = 0
    for source_id, theme, vec in embs:
        if source_id in mapped:
            continue
        mat = theme_mat.get(theme)
        if mat is None:
            skipped += 1
            continue
        idx, score = cl.nearest_centroid(np.asarray(vec, dtype=np.float32), mat)
        if idx < 0 or score < threshold:
            skipped += 1
            continue
        qid = qid_by_theme[theme][idx]
        r = decisions.get(source_id, {})
        instance_id = db.md5(sources.LOCAL_DECISION, source_id, qid)
        rows.append((instance_id, qid, sources.LOCAL_DECISION, source_id,
                     r.get("state_code"), r.get("jurisdiction_name"), r.get("city"),
                     r.get("outcome"), r.get("extracted_at"), None, float(score)))

    n = db.upsert(conn, "bronze.bronze_question_instance",
                  ["instance_id", "question_id", "source_type", "source_id", "state_code",
                   "jurisdiction_name", "city", "outcome_raw", "occurred_at", "session", "assign_score"],
                  rows, conflict_key="instance_id")
    logger.success("Assigned {} new instances ({} left unmapped, below threshold or new theme)", n, skipped)
    conn.close()
    return {"assigned": n, "unmapped": skipped}


def main() -> None:
    ap = argparse.ArgumentParser(description="Assign new decisions to existing questions.")
    ap.add_argument("--threshold", type=float, default=0.55)
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(threshold=args.threshold, database_url=args.database_url)


if __name__ == "__main__":
    main()
