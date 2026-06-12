"""
CLI: cluster decisions into policy questions (Pass A).

Within each coarse theme bucket, HDBSCAN the decision embeddings; each cluster
becomes one ``policy_question``. The canonical text + CAP topic code come from one
Gemini call per cluster (``--use-llm``) or, by default, a deterministic label
drawn from the cluster's centroid-nearest real headline. Centroids are persisted
so ``assign_instances`` can place new decisions without re-clustering.

    python -m llm.policy_questions.cluster_questions [--use-llm] [--min-cluster-size 5]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Dict, List

import numpy as np
from loguru import logger

from llm.policy_questions import cluster as cl
from llm.policy_questions import db, sources
from llm.policy_questions.coarse_theme import cofog_code
from llm.policy_questions.label_prompts import clean_question_text, question_prompt
from llm.policy_questions.labeler import Labeler


def _load_embeddings(conn, source_type: str):
    with conn.cursor() as cur:
        cur.execute(
            "select source_id, coarse_theme, embedding from bronze.bronze_pq_embedding "
            "where source_type = %s and embedding is not null",
            (source_type,),
        )
        return cur.fetchall()


def run(use_llm: bool = False, min_cluster_size: int = 5, max_llm_calls: int = 600,
        database_url: str | None = None) -> Dict[str, int]:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    labeler = Labeler(use_llm=use_llm, max_calls=max_llm_calls)

    decisions = {r["source_id"]: r for r in sources.load_decisions(conn)}
    embs = _load_embeddings(conn, sources.LOCAL_DECISION)
    by_theme: Dict[str, List[tuple]] = defaultdict(list)
    for source_id, theme, vec in embs:
        by_theme[theme or "__unthemed__"].append((source_id, np.asarray(vec, dtype=np.float32)))
    logger.info("Clustering {} decisions across {} theme buckets", len(embs), len(by_theme))

    q_rows, c_rows, i_rows = [], [], []
    n_questions = 0
    for theme, members in by_theme.items():
        if len(members) < min_cluster_size:
            continue
        ids = [m[0] for m in members]
        vectors = np.vstack([m[1] for m in members])
        labels = cl.hdbscan_labels(vectors, min_cluster_size=min_cluster_size)
        clusters = cl.build_clusters(vectors, labels, top_k_exemplars=15)
        cofog = cofog_code(theme)
        for clu in clusters:
            exemplar_rows = [decisions[ids[i]] for i in clu.exemplar_idx if ids[i] in decisions]
            exemplar_texts = [
                (r.get("headline") or r.get("decision_statement") or "")[:240] for r in exemplar_rows
            ]
            parsed = labeler.label(*question_prompt(theme, exemplar_texts), tag="pq-question") if use_llm else None
            if parsed and parsed.get("canonical_text"):
                canonical_text = clean_question_text(str(parsed["canonical_text"]))
                scope = str(parsed.get("scope") or "local")
                topic_code = (str(parsed.get("cap_topic_code")).strip() or None) if parsed.get("cap_topic_code") else None
            else:
                # heuristic: the centroid-nearest real headline (real in-data text)
                canonical_text = clean_question_text(exemplar_texts[0] if exemplar_texts else theme)
                scope, topic_code = "local", None

            question_id = db.md5(theme, canonical_text)
            member_rows = [decisions[ids[i]] for i in clu.member_idx if ids[i] in decisions]
            first_seen = min((r.get("extracted_at") for r in member_rows if r.get("extracted_at")), default=None)
            q_rows.append((question_id, canonical_text, topic_code, theme, cofog, scope,
                           "active", first_seen, len(clu.member_idx), labeler.model_tag))
            c_rows.append((question_id, theme, clu.centroid.astype(float).tolist(),
                           len(clu.member_idx), labeler.model_tag))
            for i in clu.member_idx:
                r = decisions.get(ids[i])
                if not r:
                    continue
                score = cl.cosine_to(clu.centroid, vectors[i])
                instance_id = db.md5(sources.LOCAL_DECISION, ids[i], question_id)
                i_rows.append((instance_id, question_id, sources.LOCAL_DECISION, ids[i],
                               r.get("state_code"), r.get("jurisdiction_name"), r.get("city"),
                               r.get("outcome"), r.get("extracted_at"), None, score))
            n_questions += 1

    # Rebuild: questions/centroids fully (only decisions exist in Phase 1); instances
    # scoped to this source_type. Arguments depend on questions -> clear them too.
    db.truncate(conn, "bronze.bronze_policy_question", "bronze.bronze_question_centroid",
                "bronze.bronze_canonical_argument", "bronze.bronze_instance_argument")
    with conn.cursor() as cur:
        cur.execute("delete from bronze.bronze_question_instance where source_type = %s",
                    (sources.LOCAL_DECISION,))
    conn.commit()

    db.upsert(conn, "bronze.bronze_policy_question",
              ["question_id", "canonical_text", "topic_code", "primary_theme", "cofog_code",
               "scope", "status", "first_seen", "member_count", "model_name"],
              q_rows, conflict_key="question_id")
    db.upsert(conn, "bronze.bronze_question_centroid",
              ["question_id", "coarse_theme", "centroid", "member_count", "model_name"],
              c_rows, conflict_key="question_id")
    db.upsert(conn, "bronze.bronze_question_instance",
              ["instance_id", "question_id", "source_type", "source_id", "state_code",
               "jurisdiction_name", "city", "outcome_raw", "occurred_at", "session", "assign_score"],
              i_rows, conflict_key="instance_id")
    logger.success("Built {} questions, {} instances ({} LLM calls)",
                   n_questions, len(i_rows), labeler.calls)
    conn.close()
    return {"questions": n_questions, "instances": len(i_rows), "llm_calls": labeler.calls}


def main() -> None:
    ap = argparse.ArgumentParser(description="Cluster decisions into policy questions.")
    ap.add_argument("--use-llm", action="store_true", help="Label clusters with Gemini (billed).")
    ap.add_argument("--min-cluster-size", type=int, default=5)
    ap.add_argument("--max-llm-calls", type=int, default=600)
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(use_llm=args.use_llm, min_cluster_size=args.min_cluster_size,
        max_llm_calls=args.max_llm_calls, database_url=args.database_url)


if __name__ == "__main__":
    main()
