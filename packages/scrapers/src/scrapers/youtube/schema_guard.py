"""Skip startup DDL that would queue behind long reads of the bronze YouTube tables (#534).

The catalog and caption loaders "ensure" their columns with ``ALTER TABLE … ADD COLUMN IF
NOT EXISTS`` every time they start. Postgres takes an ACCESS EXCLUSIVE lock for that ALTER
before it checks whether the column exists, so a loader that starts during a long read (a
dbt build of ``event_documents`` reading ``bronze_event_youtube``) waits behind it, and every
later reader of the table, the API included, waits behind the loader.

These helpers look in the catalog first and run DDL only when something is missing, under a
short ``lock_timeout`` so a missing column can never stall the warehouse either.
"""

from __future__ import annotations

from typing import Any, Iterable

DDL_LOCK_TIMEOUT = "5s"


def missing_columns(conn: Any, schema: str, table: str, columns: Iterable[str]) -> list[str]:
    """Return the names in ``columns`` that ``schema.table`` lacks (all of them if the table is missing)."""
    wanted = list(columns)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = ANY(%s)
            """,
            (schema, table, wanted),
        )
        present = {row[0] for row in cur.fetchall()}
    finally:
        cur.close()
    return [c for c in wanted if c not in present]


def index_exists(conn: Any, schema: str, index_name: str) -> bool:
    """True when an index named ``index_name`` exists in ``schema``."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
            (schema, index_name),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()


def is_base_table(conn: Any, relation: str) -> bool:
    """True when ``relation`` (resolved on the search path) is a table, not a view or missing."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass(%s)",
            (relation,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    return bool(row) and row[0] in ("r", "p")


def set_local_lock_timeout(cur: Any, timeout: str = DDL_LOCK_TIMEOUT) -> None:
    """Bound how long DDL in the current transaction waits for its lock."""
    cur.execute("SELECT set_config('lock_timeout', %s, true)", (timeout,))
