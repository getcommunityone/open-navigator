"""
Load the IBM-Debater ArgKP dataset from Hugging Face into bronze.

Source dataset: ``NLP-Debater-Project/IBM-Debater-ArgKP`` (single ``train`` split,
~81,638 rows). Each row is an (argument, key_point) pair under a debate ``topic``
with the argument's ``stance`` toward the topic (-1/+1) and a binary ``label``
(1 = the argument expresses that key point).

Target: ``bronze.bronze_argkp_pairs`` (idempotent upsert keyed on a content hash
of topic+argument+key_point). No SQLite fallback — the loader always targets the
configured Postgres warehouse via ``core_lib.db.resolve_target_database_url``.

    python -m ingestion.argkp.load [--limit N] [--dataset REPO] [--database-url URL]
"""

from __future__ import annotations

import argparse
import hashlib
from typing import Iterable, List, Sequence

from loguru import logger
from sqlalchemy import create_engine, text

from core_lib.db import resolve_target_database_url

DATASET = "NLP-Debater-Project/IBM-Debater-ArgKP"
SPLIT = "train"
TABLE = "bronze.bronze_argkp_pairs"

_DDL = """
create schema if not exists bronze;
create table if not exists bronze.bronze_argkp_pairs (
    pair_id    text primary key,
    topic      text not null,
    argument   text not null,
    key_point  text not null,
    stance     integer,
    label      integer,
    dataset    text,
    loaded_at  timestamptz default now()
);
create index if not exists bronze_argkp_pairs_topic_idx on bronze.bronze_argkp_pairs(topic);
create index if not exists bronze_argkp_pairs_label_idx on bronze.bronze_argkp_pairs(label);
"""

_UPSERT = text(
    """
    insert into bronze.bronze_argkp_pairs
        (pair_id, topic, argument, key_point, stance, label, dataset)
    values (:pair_id, :topic, :argument, :key_point, :stance, :label, :dataset)
    on conflict (pair_id) do update set
        stance = excluded.stance,
        label  = excluded.label,
        dataset = excluded.dataset,
        loaded_at = now()
    """
)


def _pair_id(topic: str, argument: str, key_point: str) -> str:
    return hashlib.md5(f"{topic}|{argument}|{key_point}".encode("utf-8")).hexdigest()


def _batched(rows: Sequence[dict], size: int) -> Iterable[List[dict]]:
    for i in range(0, len(rows), size):
        yield list(rows[i:i + size])


def load(limit: int | None = None, dataset: str = DATASET, database_url: str | None = None,
         batch_size: int = 1000) -> int:
    from datasets import load_dataset

    logger.info("Loading HF dataset {} (split={})", dataset, SPLIT)
    ds = load_dataset(dataset, split=SPLIT)
    if limit:
        ds = ds.select(range(min(limit, ds.num_rows)))
    logger.info("Fetched {} ArgKP pairs", ds.num_rows)

    rows: List[dict] = []
    for r in ds:
        topic = (r.get("topic") or "").strip()
        argument = (r.get("argument") or "").strip()
        key_point = (r.get("key_point") or "").strip()
        if not (topic and argument and key_point):
            continue
        rows.append({
            "pair_id": _pair_id(topic, argument, key_point),
            "topic": topic,
            "argument": argument,
            "key_point": key_point,
            "stance": r.get("stance"),
            "label": r.get("label"),
            "dataset": dataset,
        })

    engine = create_engine(database_url or resolve_target_database_url())
    written = 0
    with engine.begin() as conn:
        for stmt in _DDL.strip().split(";\n"):
            if stmt.strip():
                conn.execute(text(stmt))
    for batch in _batched(rows, batch_size):
        with engine.begin() as conn:
            conn.execute(_UPSERT, batch)
        written += len(batch)
        logger.info("  upserted {}/{}", written, len(rows))
    logger.success("Loaded {} ArgKP pairs into {}", written, TABLE)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest IBM-Debater ArgKP into bronze.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--database-url", default=None)
    ap.add_argument("--batch-size", type=int, default=1000)
    args = ap.parse_args()
    load(limit=args.limit, dataset=args.dataset, database_url=args.database_url,
         batch_size=args.batch_size)


if __name__ == "__main__":
    main()
