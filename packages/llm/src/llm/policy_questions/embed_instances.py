"""
CLI: embed instances (decisions or state bills) into ``bronze.bronze_pq_embedding``.

Idempotent — keyed on (source_type, source_id); rows whose ``embed_text_sha`` is
unchanged are skipped so re-runs are cheap and ``assign_instances`` can detect new
work. LLM-free.

    python -m llm.policy_questions.embed_instances [--source decisions|bills]
        [--state AL] [--limit N] [--full-refresh]
"""

from __future__ import annotations

import argparse
from typing import Dict

from loguru import logger

from llm.policy_questions import db, encoder, sources
from llm.policy_questions.coarse_theme import coarse_theme


def run(source: str = "decisions", state: str = "AL", limit: int | None = None,
        full_refresh: bool = False, database_url: str | None = None) -> int:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    if source == "bills":
        source_type = sources.STATE_BILL
        rows = sources.load_bills(conn, state_code=state)
        text_fn = sources.embed_text_for_bill
        theme_fn = lambda r: coarse_theme(  # noqa: E731
            f"{r.get('title') or ''} {r.get('subject_text') or ''}")
        raw_theme_fn = lambda r: r.get("subject_text") or None  # noqa: E731
        logger.info("Loaded {} {} bills", len(rows), state)
    else:
        source_type = sources.LOCAL_DECISION
        rows = sources.load_decisions(conn)
        text_fn = sources.embed_text_for
        theme_fn = lambda r: coarse_theme(r.get("primary_theme"))  # noqa: E731
        raw_theme_fn = lambda r: r.get("primary_theme")  # noqa: E731
        logger.info("Loaded {} decisions", len(rows))
    if limit:
        rows = rows[:limit]

    # existing shas to skip unchanged rows
    existing: Dict[str, str] = {}
    if not full_refresh:
        with conn.cursor() as cur:
            cur.execute(
                "select source_id, embed_text_sha from bronze.bronze_pq_embedding "
                "where source_type = %s",
                (source_type,),
            )
            existing = {sid: sha for sid, sha in cur.fetchall()}

    todo = []
    for r in rows:
        text = text_fn(r)
        if not text.strip():
            continue
        sha = db.sha256(text)
        if not full_refresh and existing.get(r["source_id"]) == sha:
            continue
        todo.append((r, text, sha))

    logger.info("Embedding {} new/changed {} ({} skipped)", len(todo), source, len(rows) - len(todo))
    if not todo:
        conn.close()
        return 0

    vectors = encoder.encode([t for _, t, _ in todo])
    name = encoder.model_name()
    dim = int(vectors.shape[1])
    out = []
    for (r, text, sha), vec in zip(todo, vectors):
        occurred = r.get("extracted_at") or r.get("latest_action_date")
        out.append((
            source_type, r["source_id"], text, sha,
            theme_fn(r), raw_theme_fn(r),
            vec.astype(float).tolist(), name, dim, occurred,
        ))
    n = db.upsert(
        conn, "bronze.bronze_pq_embedding",
        ["source_type", "source_id", "embed_text", "embed_text_sha", "coarse_theme",
         "raw_theme", "embedding", "model_name", "dim", "extracted_at"],
        out, conflict_key="source_type,source_id",
    )
    logger.success("Upserted {} embeddings (model={}, dim={})", n, name, dim)
    conn.close()
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Embed instances for the policy-question registry.")
    ap.add_argument("--source", choices=["decisions", "bills"], default="decisions")
    ap.add_argument("--state", default="AL", help="State code for --source bills.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--full-refresh", action="store_true")
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(source=args.source, state=args.state, limit=args.limit,
        full_refresh=args.full_refresh, database_url=args.database_url)


if __name__ == "__main__":
    main()
