"""
Database connection + bronze landing tables for the policy-question pipeline.

Connection resolution mirrors ``llm.gemini.persist_policy_analysis_bronze`` so the
whole package writes to the same dev warehouse. All tables live in the ``bronze``
schema (Python-owned); dbt reads them as sources and promotes to ``public``.
"""

from __future__ import annotations

import hashlib
import os
from typing import Iterable, Optional, Sequence

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values


def database_url(explicit: Optional[str] = None) -> str:
    load_dotenv()
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def connect(explicit: Optional[str] = None):
    conn = psycopg2.connect(database_url(explicit))
    conn.autocommit = False
    return conn


def md5(*parts: object) -> str:
    """Stable content hash for surrogate keys (joined by '|')."""
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# --- bronze DDL ------------------------------------------------------------

_DDL = """
create schema if not exists bronze;

create table if not exists bronze.bronze_pq_embedding (
    source_type    text not null,
    source_id      text not null,
    embed_text     text,
    embed_text_sha text,
    coarse_theme   text,
    raw_theme      text,
    embedding      double precision[],
    model_name     text,
    dim            integer,
    extracted_at   timestamptz,
    built_at       timestamptz default now(),
    primary key (source_type, source_id)
);

create table if not exists bronze.bronze_question_centroid (
    question_id  text primary key,
    coarse_theme text,
    centroid     double precision[],
    member_count integer,
    model_name   text,
    built_at     timestamptz default now()
);

-- Local-embedding assignment of canonical questions to raw transcripts (video
-- grain). High-recall semantic signal from llm.policy_questions.assign_transcripts;
-- kept distinct from the precise Gemini analysis path. PK (video_id, question_id).
create table if not exists bronze.bronze_transcript_question_match (
    video_id          text not null,
    question_id       text not null,
    score             double precision,
    n_chunks          integer,
    state_code        text,
    jurisdiction_name text,
    model_name        text,
    threshold         double precision,
    built_at          timestamptz default now(),
    primary key (video_id, question_id)
);

create table if not exists bronze.bronze_policy_question (
    question_id   text primary key,
    canonical_text text,
    topic_code    text,
    primary_theme text,
    cofog_code    text,
    scope         text,
    status        text,
    first_seen    timestamptz,
    member_count  integer,
    model_name    text,
    -- Optional alternate search terms (brand/colloquial names not in the neutral
    -- canonical_text). Promoted to public.policy_question.aliases (text[]) and
    -- matched alongside canonical_text by /search.
    aliases       text[],
    built_at      timestamptz default now()
);

-- Idempotent add for warehouses where the table predates the aliases column
-- (create-if-not-exists above won't alter an existing table).
alter table bronze.bronze_policy_question add column if not exists aliases text[];

create table if not exists bronze.bronze_canonical_argument (
    argument_id  text primary key,
    question_id  text,
    stance       text,
    label        text,
    summary      text,
    source_role  text,
    frame_id     text,
    member_count integer,
    model_name   text,
    built_at     timestamptz default now()
);

create table if not exists bronze.bronze_question_instance (
    instance_id       text primary key,
    question_id       text,
    source_type       text,
    source_id         text,
    state_code        text,
    jurisdiction_name text,
    city              text,
    outcome_raw       text,
    occurred_at       timestamptz,
    session           text,
    assign_score      double precision,
    built_at          timestamptz default now()
);

create table if not exists bronze.bronze_instance_argument (
    instance_argument_id text primary key,
    instance_id          text,
    argument_id          text,
    verbatim_excerpt     text,
    source_view          text,
    match_score          double precision,
    built_at             timestamptz default now()
);

create table if not exists bronze.bronze_question_relation (
    relation_id      text primary key,
    from_question_id text,
    to_question_id   text,
    relation_type    text,
    evidence         text,
    built_at         timestamptz default now()
);
"""


def ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_DDL)
    conn.commit()


def upsert(conn, table: str, columns: Sequence[str], rows: Iterable[Sequence], conflict_key: str) -> int:
    """Batch upsert ``rows`` into ``table`` on ``conflict_key`` (DO UPDATE)."""
    rows = list(rows)
    if not rows:
        return 0
    col_list = ", ".join(columns)
    updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in conflict_key.split(","))
    sql = (
        f"insert into {table} ({col_list}) values %s "
        f"on conflict ({conflict_key}) do update set {updates}"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows)


def truncate(conn, *tables: str) -> None:
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"truncate table {t}")
    conn.commit()
