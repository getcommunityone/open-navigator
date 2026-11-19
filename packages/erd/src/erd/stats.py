"""Measured facts about the tables an ERD draws: each table's exact row count and whether Postgres holds a primary key
on it. Only tables that exist in the schema are returned, so a model that isn't built yet says "rows not measured
yet" in the diagram rather than showing a number that was never counted."""

from __future__ import annotations

from datetime import UTC, datetime


def table_stats(dsn: str, schema: str, tables: list[str]) -> dict[str, dict]:
    """{table: {"rows": exact count(*), "pk": True if the table has a primary key constraint}} for each of `tables`
    that exists in `schema` as a table, partitioned table or materialized view. Views are skipped: they can't hold a
    primary key, and counting one can run its whole query."""
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError as exc:  # pragma: no cover - the optional `db` extra
        raise SystemExit("row counts need psycopg2: pip install 'communityone-erd[db]'") from exc

    out: dict[str, dict] = {}
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname,
                   EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'p')
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'm') AND NOT c.relispartition
               AND c.relname = ANY(%s)
            """,
            (schema, list(tables)),
        )
        found = dict(cur.fetchall())
        for name in sorted(found):
            cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(name)))
            out[name] = {"rows": int(cur.fetchone()[0]), "pk": bool(found[name])}
    return out


def measured_note(schema: str, when: datetime | None = None) -> str:
    """The legend line that says where the counts came from and when."""
    when = when or datetime.now(UTC)
    return f"row counts: exact count(*) of the {schema} tables, measured {when:%Y-%m-%d %H:%M} UTC"
