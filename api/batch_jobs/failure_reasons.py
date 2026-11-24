"""Why did these videos fail? Group ``transcript_file_error`` by reason (#792).

The Videos and Transcripts stage rows on Batch Job Status both show a failed count, and both count
``bronze.bronze_event_youtube`` rows whose ``transcript_file_error`` is not NULL
(``pipeline_stage_report``). This module reads the same rows with the same cohort and state filters,
so the reason counts add up to exactly that number.

Grouping is by keyword on the stored text. The raw text is always returned next to its group, and
text that matches no known group is "other" with its raw text, never reworded.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# (key, label, advice). The first keyword match wins, in the order of _KEYWORDS below.
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
        "network",
        "Network, proxy or VPN problem",
        "Check the VPN and the caption proxy are up, then retry.",
    ),
    (
        "not_yet_available",
        "Live event or premiere that has not started",
        "Not a failure yet: YouTube has no captions until the event happens. Retry after it ends.",
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
        "unknown",
        "No reason recorded",
        "The failure was stamped without any error text. Retry, and read the Transcripts log if it fails again.",
    ),
    (
        "other",
        "Other",
        "Not recognised. Read the raw text below; if it repeats, it needs its own group.",
    ),
]
_META = {k: (label, advice) for k, label, advice in GROUPS}

# Groups where trying again can work. The rest (no captions, private or removed) stay failed.
RETRYABLE_GROUPS = frozenset(
    {"bot_block", "rate_limit", "network", "not_yet_available", "unknown", "other"}
)

# Keyword tables, lower-case. Checked in this order against the CAUSE of the failure (see _cause).
_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("bot_block", ("sign in to confirm", "not a bot", "bot check", "bot detection")),
    ("rate_limit", ("429", "too many requests", "rate limit", "rate-limit", "quota")),
    ("not_yet_available", ("live event will begin", "premieres in", "premiere", "will begin in")),
    (
        "no_captions",
        (
            "no transcript",
            "transcripts disabled",
            "transcriptsdisabled",
            "subtitles are disabled",
            "no captions",
            "no subtitles",
            "notranscriptfound",
        ),
    ),
    (
        "unavailable",
        (
            "removed by the uploader",
            "private video",
            "video is private",
            "is a private video",
            "video unavailable",
            "unavailable",
            "has been removed",
            "removed by",
            "deleted",
            "terminated",
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

# yt-dlp and youtube-transcript-api share one opening ("Could not retrieve a transcript for the video
# <url>! This is most likely caused by: <cause> If you are sure ..."). That opening says nothing about
# the failure, so classification reads the cause and ignores the rest.
_CAUSE = re.compile(r"most likely caused by:\s*(.*?)(?:\s*if you are sure|\s*$)", re.I | re.S)
_GENERIC_OPENING = re.compile(r"could not retrieve a transcript for the video\s+\S+?!", re.I)

STAGES = ("videos", "transcripts")  # both count the same rows; see module docstring
_DIGITS = re.compile(r"[0-9]{3,}")
# A YouTube video id inside a message: only in `v=<id>` or `youtu.be/<id>` form, so an ordinary
# 11-letter word is never taken for one.
_VIDEO_ID = re.compile(r"(v=|youtu\.be/)[A-Za-z0-9_-]{11}")


def normalize_reason(text: Optional[str]) -> str:
    """Merge messages that differ only by a video id or a long number (a byte count, a port).

    Must stay identical to ``_NORM_SQL`` below, which groups in the database."""
    t = _VIDEO_ID.sub(r"\1#", (text or "").strip())
    return _DIGITS.sub("#", t)


def reason_id(normalized_reason: str) -> str:
    """Short, URL-safe id for a normalized reason: its md5, same as ``md5()`` in Postgres (UTF-8)."""
    return hashlib.md5((normalized_reason or "").encode("utf-8")).hexdigest()


def _cause(text: str) -> str:
    """The part of a message that says why it failed (the text after "most likely caused by:")."""
    m = _CAUSE.search(text)
    if m and m.group(1).strip():
        return m.group(1)
    return _GENERIC_OPENING.sub("", text)


def classify_reason(text: Optional[str]) -> str:
    """Group key for one stored error text."""
    low = (text or "").strip().lower()
    if not low:
        return "unknown"
    cause = _cause(low)
    for key, words in _KEYWORDS:
        if any(w in cause for w in words):
            return key
    return "other"


def build_groups(rows: Iterable[Tuple[Any, ...]]) -> List[Dict[str, Any]]:
    """``rows`` = (normalized reason, count, raw example[, example video id]). Groups, biggest first.

    Every input row lands in exactly one group, so the group counts sum to the input total.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        reason, count, example = row[0], row[1], row[2]
        example_video_id = (row[3] if len(row) > 3 else None) or None
        key = classify_reason(example or reason)
        buckets.setdefault(key, []).append(
            {
                "reason": reason,
                "reason_id": reason_id(reason),
                "count": int(count),
                "example": example or reason,
                "example_video_id": example_video_id,
            }
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
                "retryable": key in RETRYABLE_GROUPS,
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

# Same two steps as normalize_reason: video id first, then long numbers.
_NORM_SQL = (
    r"regexp_replace(regexp_replace(btrim(y.transcript_file_error), "
    r"'(v=|youtu\.be/)[A-Za-z0-9_-]{11}', '\1#', 'g'), '[0-9]{3,}', '#', 'g')"
)


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
                              ORDER BY y.last_updated DESC NULLS LAST))[1] AS example,
                   (array_agg(y.video_id
                              ORDER BY y.last_updated DESC NULLS LAST))[1] AS example_video_id
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
    rows = [(r[0], int(r[1]), r[2], r[3]) for r in fetched[:max_reasons]]
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
    reason_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """The failed videos behind one reason, found by its ``reason_id`` (as returned by ``failure_reasons``)."""
    jids, states, st = _scope_params(cohort, state, conn)
    out: Dict[str, Any] = {"stage": stage, "reason_id": reason_id, "total": 0, "rows": []}
    if (jids is not None and not jids) or (states is not None and not states):
        return out
    params = {
        "jids": jids,
        "states": states,
        "state": st,
        "reason_id": reason_id,
        "limit": int(limit),
        "offset": int(offset),
    }
    where = _WHERE + f" AND md5({_NORM_SQL}) = %(reason_id)s"
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


def pick_retry_reason_ids(
    groups: List[Dict[str, Any]], *, group: Optional[str] = None, reason_id: Optional[str] = None
) -> List[str]:
    """The reason ids to retry for one group or one reason. Raises ``ValueError`` when none apply,
    when both or neither selector is given, or when the group cannot be retried."""
    if bool(group) == bool(reason_id):
        raise ValueError("give exactly one of group or reason_id")
    wanted: List[str] = []
    for g in groups:
        if group and g["key"] != group:
            continue
        for r in g["reasons"]:
            if reason_id and r["reason_id"] != reason_id:
                continue
            if not g["retryable"]:
                raise ValueError(f"{g['label']!r} cannot be retried: {g['advice']}")
            wanted.append(r["reason_id"])
    if not wanted:
        raise ValueError("no failed videos match that group or reason in this scope")
    return wanted


def retry_failures(
    conn: Any,
    *,
    stage: str,
    cohort: Optional[str],
    state: Optional[str],
    group: Optional[str] = None,
    reason_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Make the failed videos of one retryable group (or one reason) due for the next fetch.

    The caption backfill skips a video for ``--retry-after-days`` after a failed attempt (the negative
    cache, ``bronze.bronze_transcript_fetch_attempts``). This sets that attempt's time back to the epoch
    for the matching videos so the next Backfill picks them up. It deletes nothing: the attempt count
    and last error stay, and the error on the video row stays until a new attempt replaces it.

    Only retryable groups are accepted. Raises ``ValueError`` for anything else.
    """
    data = failure_reasons(conn, stage=stage, cohort=cohort, state=state)
    wanted = pick_retry_reason_ids(data["groups"], group=group, reason_id=reason_id)

    jids, states, st = _scope_params(cohort, state, conn)
    params = {"jids": jids, "states": states, "state": st, "ids": wanted}
    out: Dict[str, Any] = {
        "stage": stage,
        "group": group or "",
        "reason_id": reason_id or "",
        "dry_run": bool(dry_run),
        "matched": 0,
        "made_due": 0,
        "already_due": 0,
    }
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT y.video_id FROM bronze.bronze_event_youtube y {_WHERE} "
            f"AND md5({_NORM_SQL}) = ANY(%(ids)s)",
            params,
        )
        video_ids = [r[0] for r in cur.fetchall()]
        out["matched"] = len(video_ids)
        cur.execute("SELECT to_regclass('bronze.bronze_transcript_fetch_attempts') IS NOT NULL")
        has_cache = bool(cur.fetchone()[0])
        if not video_ids or not has_cache:
            out["already_due"] = len(video_ids)
            return out
        cur.execute(
            "SELECT count(*) FROM bronze.bronze_transcript_fetch_attempts "
            "WHERE video_id = ANY(%s) AND last_attempt_at > TIMESTAMP '1970-01-02'",
            (video_ids,),
        )
        cooling = int(cur.fetchone()[0])
        out["made_due"] = cooling
        out["already_due"] = len(video_ids) - cooling
        if not dry_run and cooling:
            cur.execute(
                "UPDATE bronze.bronze_transcript_fetch_attempts SET last_attempt_at = TIMESTAMP '1970-01-01' "
                "WHERE video_id = ANY(%s) AND last_attempt_at > TIMESTAMP '1970-01-02'",
                (video_ids,),
            )
    if not dry_run:
        conn.commit()
    return out
