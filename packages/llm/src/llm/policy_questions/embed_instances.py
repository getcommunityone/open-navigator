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


class IncompatibleEmbeddingError(RuntimeError):
    """The vectors about to be written cannot be compared with the ones already stored."""


def check_embedding_compatible(
    model: str,
    dim: int,
    stored: list[tuple[str, int, int]],
    *,
    allow_model_change: bool = False,
) -> None:
    """Refuse to write vectors from a different encoder or dimension than the table holds (#885).

    ``stored`` is ``(model_name, dim, row_count)`` for what is in ``bronze.bronze_pq_embedding``.
    The encoder falls back to TF-IDF when the transformer cannot be loaded; before this check that
    fallback was written next to transformer vectors, and question assignment then failed on the
    dimension (or, worse, would have compared unrelated spaces). An empty table accepts anything.
    ``allow_model_change`` is for a deliberate switch, which must be a full refresh followed by a
    re-cluster.
    """
    others = [(m, d, c) for m, d, c in stored if (m, d) != (model, dim) and c > 0]
    if not others or allow_model_change:
        return
    main_model, main_dim, main_count = max(others, key=lambda r: r[2])
    hint = (
        " The transformer model could not be loaded, so the TF-IDF fallback was used: install "
        "torch and transformers, then run again."
        if model.endswith("+tfidf")
        else ""
    )
    raise IncompatibleEmbeddingError(
        f"Refusing to write {model} vectors of dimension {dim}: the table already holds "
        f"{main_count:,} {main_model} vectors of dimension {main_dim}, and the two cannot be "
        f"compared. Nothing was written.{hint} To switch encoders on purpose, pass "
        "--allow-model-change with --full-refresh and re-cluster afterwards."
    )


def run(source: str = "decisions", state: str = "AL", limit: int | None = None,
        full_refresh: bool = False, database_url: str | None = None,
        allow_model_change: bool = False) -> int:
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
    # Never mix encoders in one table (#885): question centroids were built with one model and one
    # dimension, and vectors from another cannot be compared with them.
    with conn.cursor() as cur:
        cur.execute(
            "select model_name, dim, count(*) from bronze.bronze_pq_embedding group by 1, 2"
        )
        stored = [(m, int(d), int(c)) for m, d, c in cur.fetchall()]
    try:
        check_embedding_compatible(name, dim, stored, allow_model_change=allow_model_change)
    except IncompatibleEmbeddingError:
        conn.close()
        raise
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
    ap.add_argument(
        "--allow-model-change", action="store_true",
        help="Write vectors from a different encoder or dimension than the table holds. "
             "Only with --full-refresh, and re-cluster afterwards.",
    )
    args = ap.parse_args()
    run(source=args.source, state=args.state, limit=args.limit,
        full_refresh=args.full_refresh, database_url=args.database_url,
        allow_model_change=args.allow_model_change)


if __name__ == "__main__":
    main()
