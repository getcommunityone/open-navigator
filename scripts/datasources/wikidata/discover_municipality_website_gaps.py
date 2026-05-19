#!/usr/bin/env python3
"""List USPS codes where municipality gazetteer rows lack *_wikidata coverage."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from scripts.datasources.wikidata.load_jurisdictions_wikidata import DATABASE_URL  # noqa: E402

GAP_SQL = """
SELECT b.usps
FROM bronze.bronze_jurisdictions_municipalities b
LEFT JOIN bronze.bronze_jurisdictions_municipalities_wikidata w
  ON w.usps = b.usps AND w.geoid::text = b.geoid::text
GROUP BY b.usps
HAVING COUNT(*) > 0 AND COUNT(w.geoid) = 0
ORDER BY b.usps
"""

LOW_URL_SQL = """
SELECT b.usps
FROM bronze.bronze_jurisdictions_municipalities b
LEFT JOIN bronze.bronze_jurisdictions_municipalities_wikidata w
  ON w.usps = b.usps AND w.geoid::text = b.geoid::text
GROUP BY b.usps
HAVING COUNT(*) > 0
   AND (
     COUNT(w.geoid) = 0
     OR COUNT(*) FILTER (
       WHERE w.official_website IS NOT NULL AND BTRIM(w.official_website::text) <> ''
     ) = 0
   )
ORDER BY b.usps
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=("no_wikidata", "no_website"),
        default="no_wikidata",
        help="no_wikidata: zero *_wikidata rows; no_website: zero shells OR zero URLs",
    )
    ap.add_argument("--database-url", default="")
    args = ap.parse_args()

    import psycopg2

    url = args.database_url.strip() or DATABASE_URL
    sql = GAP_SQL if args.mode == "no_wikidata" else LOW_URL_SQL
    conn = psycopg2.connect(url)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        states = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    print(",".join(states))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
