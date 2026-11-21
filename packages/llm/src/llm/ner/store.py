"""Bronze landing for :func:`llm.ner.spot.spot_segments` hits."""

from __future__ import annotations

from typing import Any

from loguru import logger

TABLE = "bronze.transcript_vote_phrase"

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    video_id         text NOT NULL,
    phrase_code      text NOT NULL,
    start_seconds    double precision NOT NULL,
    char_offset      integer NOT NULL,
    file_sha256      text NOT NULL,
    loaded_ts        timestamptz NOT NULL,
    git_commit_sha   text NOT NULL,
    PRIMARY KEY (file_sha256, phrase_code, start_seconds, char_offset)
)
"""

_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS bronze;"

_INSERT_COLUMNS = (
    "video_id",
    "phrase_code",
    "start_seconds",
    "char_offset",
    "file_sha256",
    "loaded_ts",
    "git_commit_sha",
)

_INSERT_SQL = (
    f"INSERT INTO {TABLE} ({', '.join(_INSERT_COLUMNS)}) "
    f"VALUES ({', '.join('%s' for _ in _INSERT_COLUMNS)})"
)


def _coerce_start_seconds(value: Any) -> float:
    """Untimed fallback segments use ``0.0`` so the primary key stays NOT NULL."""
    if value is None:
        return 0.0
    return float(value)


def _row_to_tuple(row: dict) -> tuple:
    return (
        row["video_id"],
        row["phrase_code"],
        _coerce_start_seconds(row.get("start_seconds")),
        int(row["char_offset"]),
        row["file_sha256"],
        row["loaded_ts"],
        row["git_commit_sha"],
    )


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_SCHEMA_SQL)
        cur.execute(CREATE_SQL)
    conn.commit()
    logger.debug("Ensured {}", TABLE)


def replace_hits(
    conn,
    *,
    file_sha256s: list[str],
    rows: list[dict],
) -> int:
    """Delete rows for the given transcript shas, then insert ``rows``.

    Returns the number of rows inserted.
    """
    with conn.cursor() as cur:
        if file_sha256s:
            cur.execute(
                f"DELETE FROM {TABLE} WHERE file_sha256 = ANY(%s)",
                (file_sha256s,),
            )
            logger.info(
                "Deleted prior vote-phrase rows for {} transcript sha(s)",
                len(file_sha256s),
            )
        if not rows:
            conn.commit()
            return 0
        tuples = [_row_to_tuple(r) for r in rows]
        cur.executemany(_INSERT_SQL, tuples)
        inserted = len(tuples)
    conn.commit()
    logger.success("Inserted {} vote-phrase row(s) into {}", inserted, TABLE)
    return inserted


def table_stats(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        row_count = int(cur.fetchone()[0])
        cur.execute("SELECT pg_total_relation_size(%s)", (TABLE,))
        total_bytes = int(cur.fetchone()[0])
    return {"row_count": row_count, "total_bytes": total_bytes}