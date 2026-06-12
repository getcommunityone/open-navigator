"""
CLI: build the canonical-argument library (Pass B = Key Point Analysis).

For each policy question, pool every argument snippet (problem_diagnosis /
causal_story / proposed_remedy across dominant + counter views) from its member
decisions, cluster the snippets, and turn each snippet-cluster into one
``canonical_argument`` (a "key point") with stance + Boydstun frame. Each raw
snippet maps to its key point with a cosine ``match_score``.

    python -m llm.policy_questions.cluster_arguments [--use-llm] [--min-cluster-size 4]
"""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Any, Dict, List

from loguru import logger

from llm.policy_questions import cluster as cl
from llm.policy_questions import db, encoder, sources
from llm.policy_questions.label_prompts import (
    FRAME_IDS,
    argument_prompt,
    extract_snippets,
    frame_guess,
)
from llm.policy_questions.labeler import Labeler

_ROLES = {"staff", "applicant", "resident", "official", "legislative_staff"}


def _load_question_members(conn) -> Dict[str, Dict[str, Any]]:
    """question_id -> {canonical_text, members: [source_id]}."""
    out: Dict[str, Dict[str, Any]] = {}
    with conn.cursor() as cur:
        cur.execute("select question_id, canonical_text from bronze.bronze_policy_question")
        for qid, text in cur.fetchall():
            out[qid] = {"canonical_text": text, "members": []}
        cur.execute(
            "select question_id, source_id from bronze.bronze_question_instance "
            "where source_type = %s", (sources.LOCAL_DECISION,),
        )
        for qid, sid in cur.fetchall():
            if qid in out:
                out[qid]["members"].append(sid)
    return out


def run(use_llm: bool = False, min_cluster_size: int = 4, max_llm_calls: int = 600,
        database_url: str | None = None) -> Dict[str, int]:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    labeler = Labeler(use_llm=use_llm, max_calls=max_llm_calls)
    decisions = {r["source_id"]: r for r in sources.load_decisions(conn)}
    questions = _load_question_members(conn)
    logger.info("Building arguments for {} questions", len(questions))

    arg_rows, ia_rows = [], []
    n_args = 0
    for qid, q in questions.items():
        snippets: List[Dict[str, Any]] = []
        for sid in q["members"]:
            r = decisions.get(sid)
            if not r:
                continue
            for sn in extract_snippets(r.get("competing_views")):
                sn["source_id"] = sid
                snippets.append(sn)
        if len(snippets) < min_cluster_size:
            continue
        vectors = encoder.encode([s["text"] for s in snippets])
        labels = cl.hdbscan_labels(vectors, min_cluster_size=min_cluster_size)
        clusters = cl.build_clusters(vectors, labels, top_k_exemplars=12)
        for clu in clusters:
            ex = [snippets[i] for i in clu.exemplar_idx]
            ex_texts = [s["text"][:240] for s in ex]
            members = [snippets[i] for i in clu.member_idx]
            parsed = labeler.label(*argument_prompt(q["canonical_text"], ex_texts), tag="pq-argument") if use_llm else None

            views = Counter(s["source_view"] for s in members)
            roles = Counter(s["source_role"] for s in members)
            default_stance = "pro" if views.get("dominant", 0) >= views.get("counter", 0) else "con"
            default_role = roles.most_common(1)[0][0] if roles else "staff"
            pooled_text = " ".join(s["text"] for s in members)

            if parsed and parsed.get("label"):
                label = str(parsed["label"]).strip()[:120]
                summary = str(parsed.get("summary") or "").strip()[:400]
                stance = str(parsed.get("stance") or default_stance).lower()
                stance = stance if stance in ("pro", "con") else default_stance
                role = str(parsed.get("source_role") or default_role).lower()
                role = role if role in _ROLES else default_role
                frame_id = str(parsed.get("frame_id") or "").strip()
                frame_id = frame_id if frame_id in FRAME_IDS else frame_guess(pooled_text)
            else:
                nearest = ex[0]["text"] if ex else ""
                label = " ".join(nearest.split()[:10])[:120] or "argument"
                summary = nearest[:400]
                stance, role, frame_id = default_stance, default_role, frame_guess(pooled_text)

            argument_id = db.md5(qid, label)
            arg_rows.append((argument_id, qid, stance, label, summary, role, frame_id,
                             len(clu.member_idx), labeler.model_tag))
            # one instance_argument per (decision-instance, argument); keep best match
            best: Dict[str, tuple] = {}
            for i in clu.member_idx:
                s = snippets[i]
                instance_id = db.md5(sources.LOCAL_DECISION, s["source_id"], qid)
                score = cl.cosine_to(clu.centroid, vectors[i])
                key = (instance_id, argument_id)
                if key not in best or score > best[key][1]:
                    best[key] = (s, score)
            for (instance_id, arg_id), (s, score) in best.items():
                ia_rows.append((db.md5(instance_id, arg_id), instance_id, arg_id,
                                s["text"][:600], s["source_view"], score))
            n_args += 1

    db.truncate(conn, "bronze.bronze_canonical_argument", "bronze.bronze_instance_argument")
    db.upsert(conn, "bronze.bronze_canonical_argument",
              ["argument_id", "question_id", "stance", "label", "summary", "source_role",
               "frame_id", "member_count", "model_name"],
              arg_rows, conflict_key="argument_id")
    db.upsert(conn, "bronze.bronze_instance_argument",
              ["instance_argument_id", "instance_id", "argument_id", "verbatim_excerpt",
               "source_view", "match_score"],
              ia_rows, conflict_key="instance_argument_id")
    logger.success("Built {} canonical arguments, {} instance-argument links ({} LLM calls)",
                   n_args, len(ia_rows), labeler.calls)
    conn.close()
    return {"arguments": n_args, "links": len(ia_rows), "llm_calls": labeler.calls}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build canonical arguments via Key Point Analysis.")
    ap.add_argument("--use-llm", action="store_true", help="Label key points with Gemini (billed).")
    ap.add_argument("--min-cluster-size", type=int, default=4)
    ap.add_argument("--max-llm-calls", type=int, default=600)
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(use_llm=args.use_llm, min_cluster_size=args.min_cluster_size,
        max_llm_calls=args.max_llm_calls, database_url=args.database_url)


if __name__ == "__main__":
    main()
