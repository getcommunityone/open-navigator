"""Part 1 meeting video IDs from the warehouse."""

from __future__ import annotations

import psycopg2

_PART1_SQL = """
SELECT DISTINCT m.video_id
FROM public.event_decision d
JOIN public.event_meeting m ON m.event_meeting_id = d.analysis_id
WHERE COALESCE(m.video_id, '') <> ''
ORDER BY m.video_id
"""


def list_part1_video_ids(database_url: str, *, limit: int | None = None) -> list[str]:
    """Return distinct YouTube ``video_id`` values for Part 1 analyzed meetings."""
    sql = _PART1_SQL
    params: list = []
    if limit is not None:
        sql = f"{sql}\nLIMIT %s"
        params.append(limit)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    return [str(r[0]) for r in rows]