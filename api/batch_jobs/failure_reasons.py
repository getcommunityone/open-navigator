"""Why did these videos fail? Group ``transcript_file_error`` by reason (#792).

The Videos and Transcripts stage rows on Batch Job Status both show a failed count, and both count
``bronze.bronze_event_youtube`` rows whose ``transcript_file_error`` is not NULL
(``pipeline_stage_report``). This module reads the same rows with the same cohort and state filters,
so the reason counts add up to exactly that number.

Grouping is by keyword on the stored text. The raw text is always returned next to its group, and
text that matches no known group is "other" with its raw text, never reworded.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# (key, label, advice). Order matters: the first keyword match wins.
GROUPS: List[Tuple[str, str, str]] = [
    (
        "bot_block",
        "YouTube blocked the request (bot check)",
        "Refresh youtube_cookies.txt (older than 7 days is the usual cause) and check the VPN is up, then retry.",
    ),
    (
        "rate_limit",
        "Rate limited or over quota",
        "Slow down: wait, then retry a smaller batch. Do not shorten the delay or add parallel caption fetches.",
    ),
    (
        "no_captions",
        "No captions on the video",
        "Not fixable here: the video has no transcript to download. These stay failed.",
    ),
    (
        "unavailable",
        "Video private, removed or restricted",
        "Not fixable here: the video is gone or not public. These stay failed.",
    ),
    (
        "network",
        "Network, proxy or VPN problem",
        "Check the VPN and the caption proxy are up, then retry with Backfill.",
    ),
    (
        "unknown",
        "No reason recorded",
        "The failure was stamped without any error text. Re-run the step and check its log.",
    ),
    (
        "other",
        "Other",
        "Not recognised. Read the raw text below; if it repeats, it needs its own group.",
    ),
]
_META = {k: (label, advice) for k, label, advice in GROUPS}

# Keyword tables, lower-case. Checked in this order for non-blank text.
_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("bot_block", ("sign in to confirm", "not a bot", "confirm you", "bot")),
    ("rate_limit", ("429", "too many requests", "rate limit", "rate-limit", "quota")),
    (
        "no_captions",
        (
            "no transcript",
            "transcripts disabled",
            "transcriptsdisabled",
            "subtitles are disabled",
            "no captions",
            "no subtitles",
            "could not retrieve a transcript",
            "notranscriptfound",
        ),
    ),
    (
        "unavailable",
        (
            "private video",
            "video is private",
            "is a private video",
            "video unavailable",
            "unavailable",
            "has been removed",
            "removed by",
            "deleted",
            "members-only",
            "members only",
            "age-restricted",
            "age restricted",
            "not available in your country",
        ),
    ),
    (
        "network",
        (
            "proxy",
            "timed out",
            "timeout",
            "connection",
            "ssl",
            "name resolution",
            "temporary failure",
            "vpn",
            "unreachable",
        ),
    ),
]

STAGES = ("videos", "transcripts")  # both count the same rows; see module docstring
_DIGITS = re.compile(r"[0-9]{3,}")


def normalize_reason(text: Optional[str]) -> str:
    """Merge messages that differ only by a long number (an id, a byte count, a port)."""
    return _DIGITS.sub("#", (text or "").strip())


def classify_reason(text: Optional[str]) -> str:
    """Group key for one stored error text."""
    low = (text or "").strip().lower()
    if not low:
        return "unknown"
    for key, words in _KEYWORDS:
        if any(w in low for w in words):
            return key
    return "other"


def build_groups(rows: Iterable[Tuple[str, int, str]]) -> List[Dict[str, Any]]:
    """``rows`` = (normalized reason, count, raw example). Returns groups, biggest first.

    Every input row lands in exactly one group, so the group counts sum to the input total.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for reason, count, example in rows:
        key = classify_reason(example or reason)
        buckets.setdefault(key, []).append(
            {"reason": reason, "count": int(count), "example": example or reason}
        )
    out: List[Dict[str, Any]] = []
    for key, items in buckets.items():
        items.sort(key=lambda r: r["count"], reverse=True)
        label, advice = _META[key]
        out.append(
            {
                "key": key,
                "label": label,
                "advice": advice,
                "count": sum(i["count"] for i in items),
                "reasons": items,
            }
        )
    out.sort(key=lambda g: g["count"], reverse=True)
    return out


def _scope_params(
    cohort: Optional[str], state: Optional[str], conn: Any
) -> Tuple[Optional[List[str]], Optional[List[str]], Optional[str]]:
    """Same cohort filters as the stage report, plus an optional single state."""
    from api.batch_jobs.batch_job_db import _stage_report_filters

    jids, states = _stage_report_filters(cohort, conn)
    st = (state or "").strip().upper() or None
    return jids, states, st


_WHERE = """
    WHERE y.transcript_file_error IS NOT NULL
      AND (%(jids)s::text[] IS NULL OR y.jurisdiction_id = ANY(%(jids)s))
      AND (%(states)s::text[] IS NULL OR y.state_code = ANY(%(states)s))
      AND (%(state)s::text IS NULL OR y.state_code = %(state)s)
"""

_NORM_SQL = "regexp_replace(btrim(y.transcript_file_error), '[0-9]{3,}', '#', 'g')"


def failure_reasons(
    conn: Any, *, stage: str, cohort: Optional[str], state: Optional[str], max_reasons: int = 2000
) -> Dict[str, Any]:
    """Failed videos for a stage and scope, grouped by reason. Empty groups when none failed."""
    jids, states, st = _scope_params(cohort, state, conn)
    base: Dict[str, Any] = {
        "stage": stage,
        "cohort": (cohort or "").strip().lower() or "all",
        "state": st or "",
        "total": 0,
        "truncated": False,
        "groups": [],
    }
    if (jids is not None and not jids) or (states is not None and not states):
        return base  # a cohort with no members has no failures
    params = {"jids": jids, "states": states, "state": st}
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*)::int FROM bronze.bronze_event_youtube y {_WHERE}", params)
        total = int(cur.fetchone()[0])
        cur.execute(
            f"""
            SELECT {_NORM_SQL} AS reason,
                   COUNT(*)::int AS n,
                   (array_agg(btrim(y.transcript_file_error)
                              ORDER BY y.last_updated DESC NULLS LAST))[1] AS example
            FROM bronze.bronze_event_youtube y
            {_WHERE}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT {int(max_reasons) + 1}
            """,
            params,
        )
        fetched = cur.fetchall()
    truncated = len(fetched) > max_reasons
    rows = [(r[0], int(r[1]), r[2]) for r in fetched[:max_reasons]]
    shown = sum(r[1] for r in rows)
    if truncated and total > shown:
        rows.append((f"(+{total - shown} more rows in rarer messages)", total - shown, ""))
    base.update(total=total, truncated=truncated, groups=build_groups(rows))
    return base


def failure_rows(
    conn: Any,
    *,
    stage: str,
    cohort: Optional[str],
    state: Optional[str],
    reason: str,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """The failed videos behind one normalized reason (as returned by ``failure_reasons``)."""
    jids, states, st = _scope_params(cohort, state, conn)
    out: Dict[str, Any] = {"stage": stage, "reason": reason, "total": 0, "rows": []}
    if (jids is not None and not jids) or (states is not None and not states):
        return out
    params = {
        "jids": jids,
        "states": states,
        "state": st,
        "reason": reason,
        "limit": int(limit),
        "offset": int(offset),
    }
    where = _WHERE + f" AND {_NORM_SQL} = %(reason)s"
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*)::int FROM bronze.bronze_event_youtube y {where}", params)
        out["total"] = int(cur.fetchone()[0])
        cur.execute(
            f"""
            SELECT y.video_id, y.title, y.jurisdiction_id, y.jurisdiction_name,
                   y.state_code, btrim(y.transcript_file_error)
            FROM bronze.bronze_event_youtube y
            {where}
            ORDER BY y.last_updated DESC NULLS LAST, y.video_id
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        out["rows"] = [
            {
                "video_id": r[0],
                "title": r[1] or "",
                "jurisdiction_id": r[2] or "",
                "jurisdiction_name": r[3] or "",
                "state_code": r[4] or "",
                "error": r[5] or "",
            }
            for r in cur.fetchall()
        ]
    return out
