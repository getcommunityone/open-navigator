#!/usr/bin/env python3
"""
Backfill ``persons_count`` and ``leaders_count`` on the serving stats rollup
``public.jurisdiction_state_aggregate`` for the local/dev warehouse.

Why this exists (instead of just running dbt): the dbt mart
``jurisdiction_state_aggregate`` computes these from bronze sources, but the
bronze layer is absent on the local serving DB. The serving MDM tables the
metrics ultimately describe ARE present, so we compute directly off them:

  * persons_count = COUNT(public.mdm_person)                         per geography
  * leaders_count = COUNT(public.contact_official)                   (gov/elected)
                  + COUNT(DISTINCT officer_person_uid in
                          public.mdm_bridge_person_organization
                          WHERE is_officer OR is_director_trustee
                             OR is_key_employee OR is_institutional_trustee)
                                                                      (nonprofit)
    The two leader sources are different ID namespaces and cannot be deduped
    across each other, so leaders_count SUMs the two source counts.

Geography keys: mdm_person / the bridge carry ``state_code`` + ``city_norm``
(lowercase) but NO county column, so national / state / city levels are
populated and county persons/leaders are left at 0 (matching the dbt mart).
contact_official carries ``state_code`` + ``jurisdiction`` (free-text place
name), matched to a city via lower(jurisdiction) = city_norm.

Each metric is gathered in a single GROUPING SETS scan (national + state + city
in one pass) because a per-city scan of the 13.7M-row person index is ~2 min.

Run AFTER migration 105 (which adds the columns):
    python dbt_project/scripts/backfill_persons_leaders_counts.py
"""

import psycopg2
from loguru import logger

DB_URL = "postgresql://postgres:password@localhost:5433/open_navigator"

# (is_officer OR is_director_trustee OR is_key_employee OR is_institutional_trustee)
BOARD_PREDICATE = (
    "is_officer OR is_director_trustee OR is_key_employee OR is_institutional_trustee"
)


def _fetch_grouping_sets(cursor, sql: str) -> dict:
    """
    Run a GROUPING SETS query returning (state_code, city, value) rows where a
    NULL state_code marks the national rollup and a NULL city marks a state
    rollup. Returns a dict keyed by ('national', None, None) /
    ('state', state_code, None) / ('city', state_code, city_lower).
    """
    cursor.execute(sql)
    out: dict[tuple, int] = {}
    for state_code, city, value in cursor.fetchall():
        value = int(value or 0)
        if state_code is None:
            out[("national", None, None)] = value
        elif city is None:
            out[("state", state_code, None)] = value
        else:
            out[("city", state_code, city.lower())] = value
    return out


def gather_persons(cursor) -> dict:
    logger.info("👤 Scanning public.mdm_person (national + state + city)...")
    return _fetch_grouping_sets(
        cursor,
        """
        SELECT state_code,
               NULLIF(LOWER(TRIM(city_norm)), '') AS city,
               COUNT(*) AS value
        FROM public.mdm_person
        WHERE state_code IS NOT NULL
        GROUP BY GROUPING SETS (
            (),
            (state_code),
            (state_code, NULLIF(LOWER(TRIM(city_norm)), ''))
        )
        """,
    )


def gather_board_leaders(cursor) -> dict:
    logger.info("🏛️  Scanning public.mdm_bridge_person_organization (board leaders)...")
    return _fetch_grouping_sets(
        cursor,
        f"""
        SELECT state_code,
               NULLIF(LOWER(TRIM(city_norm)), '') AS city,
               COUNT(DISTINCT officer_person_uid) AS value
        FROM public.mdm_bridge_person_organization
        WHERE state_code IS NOT NULL
          AND ({BOARD_PREDICATE})
        GROUP BY GROUPING SETS (
            (),
            (state_code),
            (state_code, NULLIF(LOWER(TRIM(city_norm)), ''))
        )
        """,
    )


def gather_official_leaders(cursor) -> dict:
    logger.info("🗳️  Scanning public.contact_official (elected/government leaders)...")
    return _fetch_grouping_sets(
        cursor,
        """
        SELECT state_code,
               NULLIF(LOWER(TRIM(jurisdiction)), '') AS city,
               COUNT(*) AS value
        FROM public.contact_official
        WHERE state_code IS NOT NULL
        GROUP BY GROUPING SETS (
            (),
            (state_code),
            (state_code, NULLIF(LOWER(TRIM(jurisdiction)), ''))
        )
        """,
    )


def main() -> None:
    logger.info("=" * 60)
    logger.info("Backfill persons_count + leaders_count → jurisdiction_state_aggregate")
    logger.info("=" * 60)

    conn = psycopg2.connect(DB_URL)
    try:
        cursor = conn.cursor()
        # The person-index scan is a full ~13.7M-row pass; lift the timeout.
        cursor.execute("SET statement_timeout = 0")

        persons = gather_persons(cursor)
        board = gather_board_leaders(cursor)
        officials = gather_official_leaders(cursor)

        # leaders = officials + nonprofit board, summed per geography key.
        keys = set(persons) | set(board) | set(officials)
        rows = []
        for key in keys:
            level, state_code, city = key
            rows.append(
                {
                    "level": level,
                    "state_code": state_code,
                    "city": city,
                    "persons": persons.get(key, 0),
                    "leaders": board.get(key, 0) + officials.get(key, 0),
                }
            )
        logger.info(
            "📊 Computed {} geography rows ({} national, {} state, {} city)",
            len(rows),
            sum(1 for r in rows if r["level"] == "national"),
            sum(1 for r in rows if r["level"] == "state"),
            sum(1 for r in rows if r["level"] == "city"),
        )

        updated = 0
        inserted = 0
        skipped = 0
        for r in rows:
            if r["persons"] == 0 and r["leaders"] == 0:
                continue

            # The serving table caps state/city at varchar(100); a few normalized
            # city values are junk (concatenated/overlong). Skip rather than abort.
            if r["level"] == "city" and (not r["city"] or len(r["city"]) > 100):
                skipped += 1
                continue
            if r["state_code"] and len(r["state_code"]) > 2:
                skipped += 1
                continue

            if r["level"] == "national":
                cursor.execute(
                    """
                    UPDATE public.jurisdiction_state_aggregate
                    SET persons_count = %s, leaders_count = %s
                    WHERE level = 'national'
                    """,
                    (r["persons"], r["leaders"]),
                )
                updated += cursor.rowcount
            elif r["level"] == "state":
                cursor.execute(
                    """
                    UPDATE public.jurisdiction_state_aggregate
                    SET persons_count = %s, leaders_count = %s
                    WHERE level = 'state'
                      AND UPPER(TRIM(state)) = UPPER(TRIM(%s))
                    """,
                    (r["persons"], r["leaders"], r["state_code"]),
                )
                updated += cursor.rowcount
            else:  # city
                cursor.execute(
                    """
                    UPDATE public.jurisdiction_state_aggregate
                    SET persons_count = %s, leaders_count = %s
                    WHERE level = 'city'
                      AND UPPER(TRIM(state)) = UPPER(TRIM(%s))
                      AND LOWER(TRIM(city)) = %s
                    """,
                    (r["persons"], r["leaders"], r["state_code"], r["city"]),
                )
                if cursor.rowcount:
                    updated += cursor.rowcount
                else:
                    cursor.execute(
                        """
                        INSERT INTO public.jurisdiction_state_aggregate
                            (level, state, city, persons_count, leaders_count)
                        VALUES ('city', %s, %s, %s, %s)
                        """,
                        (r["state_code"], r["city"], r["persons"], r["leaders"]),
                    )
                    inserted += cursor.rowcount

        conn.commit()
        logger.success(
            "✅ Done: {} rows updated, {} city rows inserted, {} skipped (overlong)",
            updated,
            inserted,
            skipped,
        )

        # Spot-check the Tuscaloosa case from the bug report.
        cursor.execute(
            """
            SELECT level, state, city, persons_count, leaders_count
            FROM public.jurisdiction_state_aggregate
            WHERE level = 'city' AND UPPER(state) = 'AL'
              AND city ILIKE '%tuscaloosa%'
            """
        )
        for row in cursor.fetchall():
            logger.info("   Tuscaloosa check → {}", row)

    except Exception as e:  # noqa: BLE001
        conn.rollback()
        logger.error("❌ Backfill failed: {}", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
