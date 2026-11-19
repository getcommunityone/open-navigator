"""Clear invented Tuscaloosa demo ``jurisdiction`` labels on ``event_meeting`` (#593).

Run (local warehouse):

    python -m llm.gemini.repair_tuscaloosa_jurisdiction --dry-run
    python -m llm.gemini.repair_tuscaloosa_jurisdiction
"""

from __future__ import annotations

import argparse
import os

from loguru import logger


_WHERE = """
em.jurisdiction IS NOT NULL
  AND (
        (
            em.jurisdiction ~* 'tuscaloosa'
            AND coalesce(em.jurisdiction_name, '') !~* 'tuscaloosa'
            AND coalesce(em.city, '') !~* 'tuscaloosa'
        )
        OR em.jurisdiction ~* '^[[:space:]]*tuscaloosa(_|[[:space:]])?0*[0-9]+[[:space:]]*$'
        OR em.jurisdiction ~* '^[[:space:]]*city_of_tuscaloosa'
      )
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("NEON_DATABASE_URL_DEV") or os.environ.get("DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.database_url:
        logger.error("Pass --database-url or set NEON_DATABASE_URL_DEV")
        return 2
    import psycopg2

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM public.event_meeting AS em WHERE {_WHERE}")
            n = cur.fetchone()[0]
            logger.info("{} event_meeting row(s) carry an invented Tuscaloosa jurisdiction", n)
            if args.dry_run or n == 0:
                return 0
            cur.execute(f"UPDATE public.event_meeting AS em SET jurisdiction = NULL WHERE {_WHERE}")
            logger.success("Cleared jurisdiction on {:,} row(s)", cur.rowcount)
        conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
