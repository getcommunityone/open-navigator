"""
Load OpenCivicData jurisdictions into bronze_jurisdiction_ocd table.

Usage:
    python -m scripts.datasources.jurisdiction_pilot.load_ocd_into_postgres \
        --database-url $NEON_DATABASE_URL_DEV
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
from pathlib import Path

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)

_OCD_CACHE = Path(__file__).resolve().parents[3] / "data" / "cache" / "opencivicdata"
_STATES = "ALABAMAALASKAARUZONAARKANSASCALIFORNIACOLORADOCONNECTICUTDELAWAREFLORIAGEORGIAHAWAIIIDAHOIS" \
          "LLINOISINDIANAIOWACAN"


def load_ocd_into_database(database_url: str) -> int:
    """
    Load all OpenCivicData jurisdictions into bronze_jurisdiction_ocd.

    Returns number of rows inserted.
    """
    if not psycopg2:
        logger.error("psycopg2 not installed")
        return 0

    if not _OCD_CACHE.exists():
        logger.error("OCD cache not found at %s", _OCD_CACHE)
        return 0

    total_inserted = 0
    conn = psycopg2.connect(database_url)

    try:
        with conn.cursor() as cur:
            # Clear existing data (optional—can comment out to preserve history)
            # cur.execute("DELETE FROM bronze.bronze_jurisdiction_ocd")

            # Load from country-us.csv (counties and base jurisdictions)
            country_csv = _OCD_CACHE / "identifiers" / "country-us.csv"
            if country_csv.exists():
                logger.info("Loading county data from %s", country_csv.name)
                with open(country_csv, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for ocd_id, name in reader:
                        if not ocd_id or not name:
                            continue

                        # Extract state code
                        if "state:" not in ocd_id:
                            continue

                        # Parse OCD ID to extract components
                        state_code = None
                        jtype = None
                        parent_ocd = None

                        for part in ocd_id.split("/"):
                            if "state:" in part:
                                state_code = part.split(":")[1].upper()
                            elif "county:" in part:
                                jtype = "county"
                            elif "place:" in part:
                                jtype = "place"
                            elif "school_district:" in part:
                                jtype = "school_district"
                                # Extract parent county if present
                                if "county:" in ocd_id:
                                    parts = ocd_id.split("county:")
                                    if len(parts) > 1:
                                        county_part = parts[1].split("/")[0]
                                        parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/county:{county_part}"

                        if not state_code or not jtype:
                            continue

                        try:
                            cur.execute(
                                """
                                INSERT INTO bronze.bronze_jurisdiction_ocd (
                                    ocd_id, state_code, jurisdiction_type, name, parent_ocd_id
                                ) VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (ocd_id) DO NOTHING
                                """,
                                (ocd_id.strip(), state_code, jtype, name.strip(), parent_ocd),
                            )
                            total_inserted += cur.rowcount
                        except Exception as exc:
                            logger.debug("Failed to insert %s: %s", ocd_id, exc)

            # Load from state-specific local_gov.csv (municipalities, districts)
            identifiers_dir = _OCD_CACHE / "identifiers" / "country-us"
            if identifiers_dir.exists():
                logger.info("Loading municipality and district data from %s", identifiers_dir)
                for state_csv in sorted(identifiers_dir.glob("state-*-local_gov.csv")):
                    state_code = state_csv.name.split("-")[1].upper()
                    logger.debug("  Loading %s", state_csv.name)

                    with open(state_csv, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        for ocd_id, name in reader:
                            if not ocd_id or not name:
                                continue

                            # Parse jurisdiction type
                            jtype = None
                            parent_ocd = None

                            if "place:" in ocd_id:
                                jtype = "place"
                            elif "county:" in ocd_id:
                                jtype = "county"
                            elif "council_district:" in ocd_id:
                                jtype = "council_district"
                                # Extract parent place
                                if "place:" in ocd_id:
                                    parts = ocd_id.split("place:")
                                    if len(parts) > 1:
                                        place_part = parts[1].split("/")[0]
                                        parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/place:{place_part}"
                            elif "ward:" in ocd_id:
                                jtype = "ward"
                                if "place:" in ocd_id:
                                    parts = ocd_id.split("place:")
                                    if len(parts) > 1:
                                        place_part = parts[1].split("/")[0]
                                        parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/place:{place_part}"

                            if not jtype:
                                continue

                            try:
                                cur.execute(
                                    """
                                    INSERT INTO bronze.bronze_jurisdiction_ocd (
                                        ocd_id, state_code, jurisdiction_type, name, parent_ocd_id
                                    ) VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (ocd_id) DO NOTHING
                                    """,
                                    (ocd_id.strip(), state_code, jtype, name.strip(), parent_ocd),
                                )
                                total_inserted += cur.rowcount
                            except Exception as exc:
                                logger.debug("Failed to insert %s: %s", ocd_id, exc)

        conn.commit()
        logger.info("Loaded %d OCD jurisdictions into bronze_jurisdiction_ocd", total_inserted)

    except Exception as exc:
        logger.error("Failed to load OCD data: %s", exc)
        conn.rollback()
    finally:
        conn.close()

    return total_inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load OpenCivicData jurisdictions into PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("DATABASE_URL"),
        help="Database URL (default: NEON_DATABASE_URL_DEV or DATABASE_URL)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.database_url:
        parser.error("--database-url required or set NEON_DATABASE_URL_DEV / DATABASE_URL")

    inserted = load_ocd_into_database(args.database_url)
    return 0 if inserted > 0 else 1


if __name__ == "__main__":
    exit(main())
