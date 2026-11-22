"""Batch-job launch cohorts: priority states, data centers, or all US states."""
from __future__ import annotations

from typing import Any, Literal, Optional, Sequence

CohortName = Literal["priority", "data_centers", "all"]
PRIORITY_STATE_CODES = ["AL", "GA", "IN", "MA", "MT", "WA", "WI"]

# 50 US states + DC — keep in sync with web_app/src/lib/usStates.ts (STATE_CODES).
ALL_STATE_CODES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]

DATA_CENTER_JURISDICTION_IDS_SQL = """
SELECT DISTINCT jurisdiction_id FROM (
  SELECT jurisdiction_id FROM intermediate.int_data_center_site__jurisdiction
  WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> ''
  UNION
  SELECT jurisdiction_id FROM public.data_center_meeting_mention
  WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> ''
) u
"""


def data_center_jurisdiction_ids(conn: Any) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(DATA_CENTER_JURISDICTION_IDS_SQL)
        return {str(r[0]) for r in cur.fetchall() if r and r[0]}


def cohort_state_codes(
    cohort: CohortName,
    *,
    conn: Any = None,
    all_states: Optional[Sequence[str]] = None,
) -> list[str]:
    if cohort == "priority":
        return list(PRIORITY_STATE_CODES)
    if cohort == "all":
        return list(all_states or ALL_STATE_CODES)
    if cohort == "data_centers":
        if conn is None:
            raise ValueError("data_centers cohort requires a database connection")
        jids = list(data_center_jurisdiction_ids(conn))
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT state_code FROM intermediate.int_jurisdictions
                WHERE jurisdiction_id = ANY(%s) AND state_code IS NOT NULL
                ORDER BY 1
                """,
                (jids,),
            )
            return [str(r[0]) for r in cur.fetchall()]
    raise ValueError(f"unknown cohort: {cohort}")


def resolve_launch_states(
    cohort: CohortName,
    states: Sequence[str],
    *,
    conn: Any = None,
) -> list[str]:
    allowed = cohort_state_codes(cohort, conn=conn)
    allowed_set = set(allowed)
    wanted = [s.strip().upper() for s in states if (s or "").strip()]
    if not wanted:
        if not allowed:
            raise ValueError(f"cohort {cohort!r} has no states")
        return list(allowed)
    bad = [s for s in wanted if s not in allowed_set]
    if bad:
        raise ValueError(f"state code(s) not in cohort {cohort!r}: {bad}")
    return wanted