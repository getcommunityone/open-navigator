"""
CLI: cluster state bills into policy questions (Phase 2, two-stage).

State legislation has a property local decisions don't: bills are frequently
near-copies — model legislation introduced across states, or the same bill
reintroduced session after session. So we cluster in two stages:

  Stage 1 (MinHash/LSH over shingled title+abstract): collapse literal near-
          duplicate bills into *families* (model-bill lineages). One exemplar per
          family feeds labeling so the LLM sees diverse bills, not 5 copies.
  Stage 2 (semantic HDBSCAN on embeddings within a coarse theme): mint one
          state-scope ``policy_question`` per cluster.

Bills map into ``question_instance`` with source_type='state_bill'. Bill
*arguments* are deferred (only abstracts are ingested today — no hearing
testimony or fiscal notes), so bill questions carry no canonical_argument rows
rather than fabricated ones.

Additive + scope-aware: only deletes its own scope='state' rows on rerun, so it
must run AFTER cluster_questions (which truncates the shared question tables).

    python -m llm.policy_questions.cluster_bills [--state AL] [--use-llm]
        [--min-cluster-size 4] [--lsh-threshold 0.8]
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

SCOPE = "state"


def _minhash(text: str, num_perm: int = 64):
    from datasketch import MinHash

    m = MinHash(num_perm=num_perm)
    words = text.split()
    shingles = {" ".join(words[i:i + 3]) for i in range(max(1, len(words) - 2))} or set(words)
    for sh in shingles:
        m.update(sh.encode("utf-8"))
    return m


def _bill_families(bills: List[dict], threshold: float) -> Dict[str, int]:
    """Union near-duplicate bills (MinHash/LSH) into family ids: source_id -> family."""
    from datasketch import MinHashLSH

    lsh = MinHashLSH(threshold=threshold, num_perm=64)
    mh: Dict[str, object] = {}
    for b in bills:
        text = sources.shingle_text_for_bill(b)
        if len(text) < 8:
            continue
        m = _minhash(text)
        mh[b["source_id"]] = m
        lsh.insert(b["source_id"], m)
    # union-find over LSH neighbours
    parent: Dict[str, str] = {sid: sid for sid in mh}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for sid, m in mh.items():
        for nb in lsh.query(m):
            parent[find(sid)] = find(nb)
    fam_ids: Dict[str, int] = {}
    fam_index: Dict[str, int] = {}
    for sid in mh:
        root = find(sid)
        fam_index.setdefault(root, len(fam_index))
        fam_ids[sid] = fam_index[root]
    return fam_ids


def run(state: str = "AL", use_llm: bool = False, min_cluster_size: int = 4,
        lsh_threshold: float = 0.8, max_llm_calls: int = 600,
        database_url: str | None = None) -> Dict[str, int]:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    labeler = Labeler(use_llm=use_llm, max_calls=max_llm_calls)

    bills = {b["source_id"]: b for b in sources.load_bills(conn, state_code=state)}
    with conn.cursor() as cur:
        cur.execute(
            "select source_id, coarse_theme, embedding from bronze.bronze_pq_embedding "
            "where source_type = %s and embedding is not null",
            (sources.STATE_BILL,),
        )
        embs = [(sid, theme, vec) for sid, theme, vec in cur.fetchall() if sid in bills]

    # Stage 1: model-bill families
    fam = _bill_families([bills[sid] for sid, _, _ in embs], lsh_threshold)
    n_families = len(set(fam.values()))
    logger.info("Stage 1: {} bills -> {} model-bill families (threshold={})",
                len(embs), n_families, lsh_threshold)

    # Stage 2: semantic clustering within coarse theme
    by_theme: Dict[str, List[tuple]] = defaultdict(list)
    for sid, theme, vec in embs:
        by_theme[theme or "__unthemed__"].append((sid, np.asarray(vec, dtype=np.float32)))
    logger.info("Stage 2: clustering {} bills across {} theme buckets", len(embs), len(by_theme))

    q_rows, c_rows, i_rows = [], [], []
    n_questions = 0
    for theme, members in by_theme.items():
        if len(members) < min_cluster_size:
            continue
        ids = [m[0] for m in members]
        vectors = np.vstack([m[1] for m in members])
        labels = cl.hdbscan_labels(vectors, min_cluster_size=min_cluster_size)
        clusters = cl.build_clusters(vectors, labels, top_k_exemplars=40)
        cofog = cofog_code(theme)
        for clu in clusters:
            # one exemplar per family so labeling sees diverse bills
            seen_fam, exemplar_texts = set(), []
            for i in clu.exemplar_idx:
                f = fam.get(ids[i])
                if f in seen_fam:
                    continue
                seen_fam.add(f)
                b = bills[ids[i]]
                exemplar_texts.append((b.get("title") or "")[:240])
                if len(exemplar_texts) >= 15:
                    break

            parsed = labeler.label(*question_prompt(theme, exemplar_texts), tag="pq-bill-question") if use_llm else None
            if parsed and parsed.get("canonical_text"):
                canonical_text = clean_question_text(str(parsed["canonical_text"]))
                topic_code = (str(parsed.get("cap_topic_code")).strip() or None) if parsed.get("cap_topic_code") else None
            else:
                canonical_text = clean_question_text(exemplar_texts[0] if exemplar_texts else theme)
                topic_code = None

            question_id = db.md5(SCOPE, theme, canonical_text)
            member_rows = [bills[ids[i]] for i in clu.member_idx]
            first_seen = min((r.get("latest_action_date") for r in member_rows if r.get("latest_action_date")), default=None)
            q_rows.append((question_id, canonical_text, topic_code, theme, cofog, SCOPE,
                           "active", first_seen, len(clu.member_idx), labeler.model_tag))
            c_rows.append((question_id, theme, clu.centroid.astype(float).tolist(),
                           len(clu.member_idx), labeler.model_tag))
            for i in clu.member_idx:
                b = bills[ids[i]]
                score = cl.cosine_to(clu.centroid, vectors[i])
                instance_id = db.md5(sources.STATE_BILL, ids[i], question_id)
                i_rows.append((instance_id, question_id, sources.STATE_BILL, ids[i],
                               b.get("state_code"), b.get("state_code"), None,
                               b.get("latest_action_description"), b.get("latest_action_date"),
                               b.get("session_identifier"), score))
            n_questions += 1

    # Dedupe by PK: heuristic labels (shared AL bill-title prefixes) can land two
    # clusters on the same question_id; merge them (a single upsert batch cannot
    # touch the same conflict key twice).
    q_rows = list({r[0]: r for r in q_rows}.values())
    c_rows = list({r[0]: r for r in c_rows}.values())
    i_rows = list({r[0]: r for r in i_rows}.values())

    # Additive rebuild: clear only this scope's rows (decisions untouched).
    with conn.cursor() as cur:
        cur.execute("delete from bronze.bronze_question_instance where source_type = %s",
                    (sources.STATE_BILL,))
        cur.execute(
            "delete from bronze.bronze_question_centroid where question_id in "
            "(select question_id from bronze.bronze_policy_question where scope = %s)", (SCOPE,))
        cur.execute("delete from bronze.bronze_policy_question where scope = %s", (SCOPE,))
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
    logger.success("Built {} state questions, {} bill instances, {} families ({} LLM calls)",
                   n_questions, len(i_rows), n_families, labeler.calls)
    conn.close()
    return {"questions": n_questions, "instances": len(i_rows), "families": n_families,
            "llm_calls": labeler.calls}


def main() -> None:
    ap = argparse.ArgumentParser(description="Cluster state bills into policy questions.")
    ap.add_argument("--state", default="AL")
    ap.add_argument("--use-llm", action="store_true", help="Label clusters with Gemini (billed).")
    ap.add_argument("--min-cluster-size", type=int, default=4)
    ap.add_argument("--lsh-threshold", type=float, default=0.8)
    ap.add_argument("--max-llm-calls", type=int, default=600)
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(state=args.state, use_llm=args.use_llm, min_cluster_size=args.min_cluster_size,
        lsh_threshold=args.lsh_threshold, max_llm_calls=args.max_llm_calls,
        database_url=args.database_url)


if __name__ == "__main__":
    main()
