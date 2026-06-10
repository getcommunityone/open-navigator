"""
CLI: embed decisions into ``bronze.bronze_pq_embedding``.

Idempotent — keyed on (source_type, source_id); rows whose ``embed_text_sha`` is
unchanged are skipped so re-runs are cheap and ``assign_instances`` can detect new
work. LLM-free.

    python -m llm.policy_questions.embed_instances [--limit N] [--full-refresh]
"""

from __future__ import annotations

import argparse
from typing import Dict

from loguru import logger

from llm.policy_questions import db, encoder, sources
from llm.policy_questions.coarse_theme import coarse_theme


def run(limit: int | None = None, full_refresh: bool = False, database_url: str | None = None) -> int:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    rows = sources.load_decisions(conn)
    if limit:
        rows = rows[:limit]
    logger.info("Loaded {} decisions", len(rows))

    # existing shas to skip unchanged rows
    existing: Dict[str, str] = {}
    if not full_refresh:
        with conn.cursor() as cur:
            cur.execute(
                "select source_id, embed_text_sha from bronze.bronze_pq_embedding "
                "where source_type = %s",
                (sources.LOCAL_DECISION,),
            )
            existing = {sid: sha for sid, sha in cur.fetchall()}

    todo = []
    for r in rows:
        text = sources.embed_text_for(r)
        sha = db.sha256(text)
        if not full_refresh and existing.get(r["source_id"]) == sha:
            continue
        todo.append((r, text, sha))

    logger.info("Embedding {} new/changed decisions ({} skipped)", len(todo), len(rows) - len(todo))
    if not todo:
        conn.close()
        return 0

    vectors = encoder.encode([t for _, t, _ in todo])
    name = encoder.model_name()
    dim = int(vectors.shape[1])
    out = []
    for (r, text, sha), vec in zip(todo, vectors):
        out.append((
            r["source_type"], r["source_id"], text, sha,
            coarse_theme(r.get("primary_theme")), r.get("primary_theme"),
            vec.astype(float).tolist(), name, dim, r.get("extracted_at"),
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
    ap = argparse.ArgumentParser(description="Embed decisions for the policy-question registry.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--full-refresh", action="store_true")
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(limit=args.limit, full_refresh=args.full_refresh, database_url=args.database_url)


if __name__ == "__main__":
    main()
