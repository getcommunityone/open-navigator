"""
Civic-topic catalog API — GET /api/topics.

Serves the topic taxonomy (public.civicsearch_topic): a small, fixed list of
named topics, each with its query slug and the keyword set used to recall it.
Most are CivicSearch's (~75); a few are hand-curated (source = 'curated',
topic_id >= 100000, e.g. "Data centers", issue #500).

GET /api/topics/{topic_id}/meetings lists the meetings a curated topic's
keywords matched, each with a stored, highlighted verbatim passage
(public.topic_transcript_link, cut in dbt because production event_documents
carries no transcript content, #496). Reads the published serving view over gold
(resolves as public.civicsearch_topic / gold.civicsearch_topic via the
connection search_path, matching the other routes).

asyncpg gotcha: the pool has no JSONB codec, so `keyword_stats` arrives as a
TEXT blob and must be json.loads()'d before it is a real list.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Literal, Optional

import asyncpg

from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.decision_people import DecisionPeople
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)


class TopicSummary(BaseModel):
    topic_id: int
    name: str
    query_id: Optional[str] = None
    keywords: List[str] = []
    # How many CivicSearch transcript snippets are tagged with this topic — the
    # "how often it comes up" signal the catalog is sorted by (desc).
    transcript_occurrences: int = 0
    # 'civicsearch' (CivicSearch taxonomy) or 'curated' (hand-authored, #500).
    source: str = "civicsearch"
    # Meetings (transcripts) whose text matched the topic, in the requested scope:
    # national / state / city (state+city → place grain). None = no count row.
    meeting_count: Optional[int] = None


# Sorted by transcript occurrences (most-discussed first) so the browse flyout's
# top-N is the topics that actually come up most in the record; name breaks ties.
# keyword_stats is JSONB (returned as TEXT by this pool) — parsed below.
#
# $2 = optional 2-letter state code. $3 = optional city / jurisdiction ILIKE
# pattern (e.g. '%Atlanta%'); $4 = the bare city, to prefer an exact name match. When $3 is set, meeting_count and the existence
# filter come from browse_entity_place_transcript_count (city grain, #590).
# Otherwise: browse_transcript_count (national) or browse_entity_state_… ($2).
_TOPICS_SQL = """
    SELECT t.topic_id, t.name, t.query_id, t.keyword_stats, t.transcript_occurrences,
           -- Defensive read: works before the `source` column reaches Neon.
           to_jsonb(t) ->> 'source' AS source,
           CASE
                WHEN $3::text IS NOT NULL THEN (
                    -- One place (#1026): "%Tuscaloosa%" also matches "Tuscaloosa City School District", and a
                    -- scalar subquery with two rows errors. Prefer the exact city name ($4), then the most meetings.
                    SELECT p.transcript_count FROM browse_entity_place_transcript_count p
                    WHERE p.entity_type = 'topic' AND p.entity_id = t.topic_id::text
                      AND p.state_code = $2::text
                      AND p.jurisdiction_name ILIKE $3::text
                    ORDER BY (lower(p.jurisdiction_name) = lower($4::text)) DESC, p.transcript_count DESC
                    LIMIT 1
                )
                WHEN $2::text IS NULL THEN (
                    SELECT n.transcript_count FROM browse_transcript_count n
                    WHERE n.entity_type = 'topic' AND n.entity_id = t.topic_id::text
                ) ELSE (
                    SELECT s.transcript_count FROM browse_entity_state_transcript_count s
                    WHERE s.entity_type = 'topic' AND s.entity_id = t.topic_id::text
                      AND s.state_code = $2::text
                ) END AS meeting_count
    FROM civicsearch_topic t
    WHERE ($1::text IS NULL OR t.name ILIKE $1)
      AND ($2::text IS NULL OR $3::text IS NOT NULL OR EXISTS (
            SELECT 1 FROM browse_entity_state_transcript_count b
            WHERE b.entity_type = 'topic'
              AND b.entity_id = t.topic_id::text
              AND b.state_code = $2::text
      ))
      AND ($3::text IS NULL OR EXISTS (
            SELECT 1 FROM browse_entity_place_transcript_count bp
            WHERE bp.entity_type = 'topic'
              AND bp.entity_id = t.topic_id::text
              AND bp.state_code = $2::text
              AND bp.jurisdiction_name ILIKE $3::text
      ))
    ORDER BY t.transcript_occurrences DESC NULLS LAST, t.name ASC
"""


def _parse_keywords(raw) -> List[str]:
    """Coerce the JSONB keyword_stats column into a clean list[str].

    The pool hands JSONB back as a TEXT string, so json.loads it; tolerate an
    already-parsed list, a null, or malformed JSON (-> empty list) rather than
    500-ing the whole catalog over one bad row.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(k) for k in raw]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if isinstance(parsed, list):
        return [str(k) for k in parsed]
    return []


@router.get("", response_model=List[TopicSummary])
async def list_topics(
    q: Optional[str] = Query(None, description="Optional case-insensitive substring filter on topic name."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code; restricts to topics discussed in that state."),
    city: Optional[str] = Query(
        None,
        description="Optional city / jurisdiction name; with state, meeting_count is city grain (#590).",
    ),
) -> List[TopicSummary]:
    """Civic topics (most-discussed first), optionally narrowed by name, state,
    and/or city (city grain uses browse_entity_place_transcript_count)."""
    with tracer.start_as_current_span("topics-list") as span:
        span.set_attribute("topics.q", (q or "").strip())
        like = f"%{q.strip()}%" if q and q.strip() else None
        # Normalize to the 2-letter upper-case form the bridge stores; blank -> None.
        state_code = state.strip().upper() if state and state.strip() else None
        city_like = f"%{city.strip()}%" if city and city.strip() else None
        # City grain needs a state; ignore a lone city rather than invent a scope.
        if city_like and not state_code:
            city_like = None
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", (city or "").strip())
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("topics-query"):
                    rows = await conn.fetch(
                        _TOPICS_SQL, like, state_code, city_like, (city or '').strip() if city_like else None
                    )
        except Exception as exc:  # noqa: BLE001
            logger.exception("topics list failed")
            span.record_exception(exc)
            # A failed query is not "no topics": say so, so Browse Topics shows
            # "Couldn't load topics" instead of a blank row and a dead dropdown.
            raise HTTPException(status_code=503, detail="Topics are unavailable right now.") from exc

        span.set_attribute("topics.count", len(rows))
        return [
            TopicSummary(
                topic_id=r["topic_id"],
                name=r["name"],
                query_id=r["query_id"],
                keywords=_parse_keywords(r["keyword_stats"]),
                transcript_occurrences=r["transcript_occurrences"] or 0,
                source=r["source"] or "civicsearch",
                meeting_count=r["meeting_count"],
            )
            for r in rows
        ]


class TopicMeeting(BaseModel):
    video_id: str
    title: Optional[str] = None
    # Bare ISO date string (YYYY-MM-DD) or None.
    date: Optional[str] = None
    state_code: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    video_url: Optional[str] = None
    # Verbatim transcript passage with the matched words wrapped in <mark>…</mark>
    # (render with highlightSnippet, never as raw HTML).
    excerpt: Optional[str] = None
    n_keyword_hits: int = 0
    # Who said the passage, from their self-introduction in the recording (#1231): an official's name, a resident's
    # "First L.", or null (unknown, or withheld for a student, a minor or a school board resident). Filled on
    # /states `newest` only.
    speaker_display_name: Optional[str] = None
    speaker_role: Optional[str] = None
    # How the public leaned at this meeting in the AI reading (topic_meeting_lean, #1230; on /meetings since #1293):
    # 'against' / 'for' (P >= 0.7), 'split' (mixed, or a lean under 0.7), 'silent' (read; the public didn't speak on it)
    # or None (not read). Same thresholds as the map. Never a count of speakers.
    public_stance: Optional[str] = None
    # /meetings only (#1293). The meeting's five-position public reading (water fluoridation: 'oppose_local_choice', ...),
    # served only when it agrees with `public_stance`'s side; None otherwise.
    public_position: Optional[str] = None
    # What the council or board did on the topic at this meeting, in the same AI reading (topic_meeting_lean.outcome_group,
    # the Votes screen's source): 'advanced' | 'blocked' | 'tabled_or_deferred', or None.
    vote: Optional[str] = None
    # The card's position chip, from the most specific real source: 'speaker' (the quoted speaker's own stance; no
    # per-passage stance is published yet, so never set today), 'meeting' (the meeting's overall public position: a
    # `public_stance` of against/for/split, or the matching `public_position`), 'vote' (the body's action, `vote`).
    # Both None when there is no source: no chip.
    position: Optional[str] = None
    position_source: Optional[Literal["speaker", "meeting", "vote"]] = None
    # Named public commenters whose own words in this meeting matched the topic (meeting_comment.topic_ids): "First L."
    # at most, never a possible minor, never at a school-board meeting. Up to 3 names; `commenter_count` is all of them.
    commenters: List[str] = []
    commenter_count: int = 0
    # No person, no public position and no vote on record: the card goes under "Mentioned in passing".
    in_passing: bool = False
    # The meeting's page in the app (/meetings/{event_meeting_id}) when the recording has one; None otherwise.
    meeting_url: Optional[str] = None


class TopicSaidCounts(BaseModel):
    """Distinct meetings in scope by what the record says about people and positions (#1293). Never speakers."""

    # The meeting's public position in the AI reading (same thresholds as the map).
    against: int = 0
    for_: int = Field(0, alias="for")
    split: int = 0
    silent: int = 0
    # No AI reading of the meeting yet.
    unread: int = 0
    # What the body did, where the reading says it acted.
    vote_advanced: int = 0
    vote_blocked: int = 0
    vote_tabled: int = 0
    # Meetings whose card names a person (the quoted speaker or a named commenter).
    with_person: int = 0
    # against + for + split.
    public_position_meetings: int = 0
    # No person, no public position, no vote.
    in_passing: int = 0

    model_config = {"populate_by_name": True}


class TopicMeetingList(BaseModel):
    topic_id: int
    total: int
    items: List[TopicMeeting]
    # /meetings: the scope's meetings by people and position (#1293). None when the serving copy lacks the tables.
    position_counts: Optional[TopicSaidCounts] = None


_TOPIC_MEETINGS_WHERE = """
    WHERE l.topic_id = $1
      AND ($2::text IS NULL OR l.state_code = $2::text)
      AND ($3::text IS NULL OR l.city ILIKE $3::text OR l.jurisdiction_name ILIKE $3::text)
"""

_TOPIC_MEETINGS_SQL = f"""
    SELECT l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
           l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits
    FROM topic_transcript_link l
    {_TOPIC_MEETINGS_WHERE}
    ORDER BY l.event_date DESC NULLS LAST, l.n_keyword_hits DESC, l.video_id
    LIMIT $4 OFFSET $5
"""

_TOPIC_MEETINGS_COUNT_SQL = f"""
    SELECT count(*) FROM topic_transcript_link l
    {_TOPIC_MEETINGS_WHERE}
"""


# --- people and position on "What was said" (#1293) ---------------------------------------------------------------------
#
# The same scoped links, each joined to what the record says about who spoke and where people stood:
#   lean  the meeting's AI reading (topic_meeting_lean): the public's stance (map thresholds), its five-position reading,
#         and what the body did (outcome_group; a keyword false hit, excluded_no_item, has no vote and no public side);
#   spk   the quoted passage's speaker from their self-introduction (meeting_passage_speaker, #1231/#1245; suppressed and
#         unrecognized introductions carry no name, so they never show);
#   com   named public commenters whose own words matched the topic (meeting_comment.topic_ids): never a possible minor,
#         never staff or an applicant (is_public_comment), never at a school-board meeting (the meeting_speaker_intro rule:
#         a school_district jurisdiction, or a jurisdiction or title naming a school board).
_SCHOOL_JURIS_RE = r"(school|\misd\M|\musd\M|board\s+of\s+ed)"
_SCHOOL_TITLE_RE = (
    r"(schools?\s+board|school\s+district|school\s+committee|board\s+of\s+ed|\mboe\M|\musd\M|\misd\M"
    r"|board\s+of\s+trustees.*school|student)"
)

_SAID_CTE = f"""
    WITH scoped AS (
        SELECT l.* FROM topic_transcript_link l
        {_TOPIC_MEETINGS_WHERE}
    ),
    lean AS (
        SELECT t.video_id,
               CASE
                   WHEN t.public_lean IS NULL THEN NULL
                   WHEN coalesce(t.excluded_no_item, false) OR t.public_lean = 'did_not_speak' THEN 'silent'
                   WHEN t.public_against THEN 'against'
                   WHEN t.public_for THEN 'for'
                   WHEN t.public_lean IN ('mixed', 'mostly_opposed', 'mostly_supportive') THEN 'split'
               END AS public_stance,
               CASE WHEN NOT coalesce(t.excluded_no_item, false) THEN t.public_position END AS public_position,
               CASE
                   WHEN NOT coalesce(t.excluded_no_item, false)
                    AND t.outcome_group IN ('advanced', 'blocked', 'tabled_or_deferred') THEN t.outcome_group
               END AS vote
        FROM topic_meeting_lean t
        WHERE t.topic_id = $1 AND t.video_id IN (SELECT video_id FROM scoped)
    ),
    spk AS (
        SELECT DISTINCT ON (s.topic_transcript_link_id)
               s.topic_transcript_link_id, s.speaker_kind, s.speaker_display_name, s.speaker_role
        FROM meeting_passage_speaker s
        WHERE s.topic_transcript_link_id IN (SELECT topic_transcript_link_id FROM scoped)
          AND s.speaker_display_name IS NOT NULL AND s.attribution_tier <> 'low'
        ORDER BY s.topic_transcript_link_id, s.meeting_passage_speaker_id
    ),
    com AS (
        SELECT c.video_id,
               count(DISTINCT c.speaker_display_name)::int AS commenter_count,
               (array_agg(c.speaker_display_name ORDER BY c.comment_index, c.speaker_display_name))[1:12] AS commenters
        FROM meeting_comment c
        JOIN scoped sc ON sc.video_id = c.video_id
        LEFT JOIN jurisdictions j ON j.jurisdiction_id = c.jurisdiction_id
        WHERE $1 = ANY(c.topic_ids)
          AND c.is_public_comment
          AND NOT coalesce(c.possible_minor, false)
          AND c.speaker_display_name IS NOT NULL
          AND coalesce(j.jurisdiction_type, '') <> 'school_district'
          AND coalesce(sc.jurisdiction_name, '') !~* '{_SCHOOL_JURIS_RE}'
          AND coalesce(c.jurisdiction_name, '') !~* '{_SCHOOL_JURIS_RE}'
          AND coalesce(sc.event_title, '') !~* '{_SCHOOL_TITLE_RE}'
        GROUP BY c.video_id
    ),
    said AS (
        SELECT sc.*, lean.public_stance, lean.public_position, lean.vote,
               spk.speaker_kind, spk.speaker_display_name, spk.speaker_role,
               coalesce(com.commenter_count, 0) AS commenter_count, com.commenters,
               (spk.speaker_display_name IS NOT NULL OR coalesce(com.commenter_count, 0) > 0) AS has_person,
               CASE
                   WHEN lean.public_stance IN ('against', 'for', 'split') THEN 0
                   WHEN lean.vote IS NOT NULL OR spk.speaker_display_name IS NOT NULL
                        OR coalesce(com.commenter_count, 0) > 0 THEN 1
                   ELSE 2
               END AS said_rank
        FROM scoped sc
        LEFT JOIN lean ON lean.video_id = sc.video_id
        LEFT JOIN spk ON spk.topic_transcript_link_id = sc.topic_transcript_link_id
        LEFT JOIN com ON com.video_id = sc.video_id
    )
"""

# $6 = 'people' puts meetings where the public took a position first, then a vote or a named person, then the rest; a
# named person first within each group; newest first after that. Anything else keeps the newest-first order.
_SAID_ITEMS_SQL = _SAID_CTE + """
    SELECT * FROM said
    ORDER BY CASE WHEN $6::text = 'people' THEN said_rank ELSE 0 END,
             CASE WHEN $6::text = 'people' AND has_person THEN 0 ELSE 1 END,
             event_date DESC NULLS LAST, n_keyword_hits DESC, video_id
    LIMIT $4 OFFSET $5
"""

_SAID_COUNTS_SQL = _SAID_CTE + """
    SELECT count(*)::int AS total,
           count(*) FILTER (WHERE public_stance = 'against')::int AS against,
           count(*) FILTER (WHERE public_stance = 'for')::int AS for_,
           count(*) FILTER (WHERE public_stance = 'split')::int AS split,
           count(*) FILTER (WHERE public_stance = 'silent')::int AS silent,
           count(*) FILTER (WHERE public_stance IS NULL)::int AS unread,
           count(*) FILTER (WHERE vote = 'advanced')::int AS vote_advanced,
           count(*) FILTER (WHERE vote = 'blocked')::int AS vote_blocked,
           count(*) FILTER (WHERE vote = 'tabled_or_deferred')::int AS vote_tabled,
           count(*) FILTER (WHERE has_person)::int AS with_person,
           count(*) FILTER (WHERE said_rank = 0)::int AS public_position_meetings,
           count(*) FILTER (WHERE said_rank = 2)::int AS in_passing
    FROM said
"""

SAID_SORTS = ("newest", "people")

_SAID_MEETING_PAGE_SQL = """
    SELECT DISTINCT ON (e.video_id) e.video_id, e.event_meeting_id
    FROM event_meeting e WHERE e.video_id = ANY($1::text[])
    ORDER BY e.video_id, e.event_meeting_id
"""


async def said_meeting_urls(conn: Any, video_ids: List[str]) -> dict[str, str]:
    """The meeting page (/meetings/{event_meeting_id}) for each recording on the page, or {} without event_meeting."""
    if not video_ids:
        return {}
    try:
        rows = await conn.fetch(_SAID_MEETING_PAGE_SQL, video_ids)
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("topic meetings: event_meeting unavailable ({}); no meeting links", e)
        return {}
    return {str(r["video_id"]): f"/meetings/{r['event_meeting_id']}" for r in rows if r["event_meeting_id"] is not None}

# Which side each five-position key is on (water fluoridation, llm.typesafe.topic_lean).
_FIVE_SIDE = {
    "support_require_all": "for",
    "support_local_choice": "for",
    "oppose_local_choice": "against",
    "oppose_ban_all": "against",
}


def said_position(
    public_stance: Optional[str], public_position: Optional[str], vote: Optional[str]
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(position, position_source, public_position) for one card (#1293), from the most specific real source.

    No per-passage speaker stance is published, so 'speaker' never comes from here. The meeting's public position comes
    next: against / for / split from the AI reading (the map's thresholds); for a five-position topic the finer reading is
    used only when it is on the same side, so the chip never contradicts the counts. Then what the body did (`vote`).
    Nothing else: no source, no chip."""
    five = public_position if public_position in _FIVE_SIDE and _FIVE_SIDE[public_position] == public_stance else None
    if public_stance in ("against", "for"):
        return (five or public_stance), "meeting", five
    if public_stance == "split":
        return "split", "meeting", None
    if vote in ("advanced", "blocked", "tabled_or_deferred"):
        return vote, "vote", None
    return None, None, None


def commenter_names(raw: Optional[List[Any]], limit: int = 3, exclude: Optional[str] = None) -> List[str]:
    """Distinct commenter names in speaking order, each cut to "First L." at most again here (AGENTS.md, Privacy). The
    quoted passage's own speaker (`exclude`) is left out, as the card names them already."""
    out: List[str] = []
    for n in raw or []:
        name, _ = speaker_fields({"speaker_display_name": n, "speaker_kind": "resident"})
        if name and name != exclude and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def said_meeting(r: Any) -> "TopicMeeting":
    """One "What was said" card from a `_SAID_ITEMS_SQL` row."""
    position, source, five = said_position(r.get("public_stance"), r.get("public_position"), r.get("vote"))
    name, role = speaker_fields(
        {
            "speaker_display_name": r.get("speaker_display_name"),
            "speaker_kind": r.get("speaker_kind"),
            "speaker_role": r.get("speaker_role"),
        }
        if r.get("speaker_display_name")
        else None
    )
    commenters = commenter_names(r.get("commenters"), exclude=name)
    count = int(r.get("commenter_count") or 0) - (1 if name and name in commenter_names(r.get("commenters"), limit=99) else 0)
    return TopicMeeting(
        video_id=r["video_id"],
        title=r["event_title"],
        date=r["event_date"].isoformat() if r["event_date"] else None,
        state_code=r["state_code"],
        state=r["state"],
        city=r["city"],
        jurisdiction_name=r["jurisdiction_name"],
        video_url=r["video_url"],
        excerpt=r["evidence_passage"],
        n_keyword_hits=r["n_keyword_hits"] or 0,
        speaker_display_name=name,
        speaker_role=role,
        public_stance=r.get("public_stance"),
        public_position=five,
        vote=r.get("vote"),
        position=position,
        position_source=source,  # type: ignore[arg-type]
        commenters=commenters,
        commenter_count=max(count, len(commenters)),
        meeting_url=r.get("meeting_url"),
        in_passing=r.get("said_rank") == 2,
    )


def said_counts(row: Optional[Any]) -> Optional[TopicSaidCounts]:
    if not row:
        return None
    d = dict(row)
    d.pop("total", None)
    return TopicSaidCounts(**{k: int(v or 0) for k, v in d.items()})


@router.get("/{topic_id}/meetings", response_model=TopicMeetingList)
async def list_topic_meetings(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
    city: Optional[str] = Query(None, description="Optional city / jurisdiction name (ILIKE)."),
    limit: int = Query(12, ge=1, le=60, description="Page size (1..60)."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
    sort: str = Query(
        "newest",
        description="'newest' (default) or 'people' (#1293): meetings where the public took a position first, then a "
        "vote or a named person, then passages mentioning it in passing; newest first within each.",
    ),
) -> TopicMeetingList:
    """Meetings whose transcript matched a curated topic's keywords, each with its highlighted verbatim passage, who said
    it where the record names them, and the card's position chip from the most specific real source (#1293). Empty
    (total 0) for a topic without stored links (the CivicSearch topics) or an empty scope."""
    with tracer.start_as_current_span("topic-meetings") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        city_like = f"%{city.strip()}%" if city and city.strip() else None
        order = sort if sort in SAID_SORTS else "newest"
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", (city or "").strip())
        span.set_attribute("topics.sort", order)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                try:
                    with tracer.start_as_current_span("topic-meetings.said"):
                        # The counts (and the total) are the scope's: read with the first page; later pages count only.
                        counts_row = (
                            await conn.fetchrow(_SAID_COUNTS_SQL, topic_id, state_code, city_like)
                            if offset == 0
                            else {"total": await conn.fetchval(_TOPIC_MEETINGS_COUNT_SQL, topic_id, state_code, city_like)}
                        )
                        said_rows = await conn.fetch(
                            _SAID_ITEMS_SQL, topic_id, state_code, city_like, limit, offset, order
                        )
                    urls = await said_meeting_urls(conn, [r["video_id"] for r in said_rows])
                    items = [said_meeting({**dict(r), "meeting_url": urls.get(r["video_id"])}) for r in said_rows]
                    counts = said_counts(counts_row) if offset == 0 else None
                    span.set_attribute("topics.meetings_with_person", sum(1 for i in items if i.speaker_display_name or i.commenters))
                    span.set_attribute("topics.meetings_with_position", sum(1 for i in items if i.position))
                    return TopicMeetingList(
                        topic_id=topic_id,
                        total=int((counts_row or {}).get("total") or 0),
                        items=items,
                        position_counts=counts,
                    )
                except asyncpg.exceptions.PostgresError as e:
                    # A serving copy without the lean / speaker / comment tables (or a column): the plain list.
                    logger.warning("topic meetings: people/position tables unavailable ({}); plain list", e)
                total = await conn.fetchval(
                    _TOPIC_MEETINGS_COUNT_SQL, topic_id, state_code, city_like
                )
                rows = await conn.fetch(
                    _TOPIC_MEETINGS_SQL, topic_id, state_code, city_like, limit, offset
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic meetings failed")
            span.record_exception(exc)
            # A failed query is not "no meetings" (#816): the list component shows its error state.
            raise HTTPException(
                status_code=503, detail="Meetings for this topic are unavailable right now."
            ) from exc

        span.set_attribute("topics.meetings_total", int(total or 0))
        return TopicMeetingList(
            topic_id=topic_id,
            total=int(total or 0),
            items=[
                TopicMeeting(
                    video_id=r["video_id"],
                    title=r["event_title"],
                    date=r["event_date"].isoformat() if r["event_date"] else None,
                    state_code=r["state_code"],
                    state=r["state"],
                    city=r["city"],
                    jurisdiction_name=r["jurisdiction_name"],
                    video_url=r["video_url"],
                    excerpt=r["evidence_passage"],
                    n_keyword_hits=r["n_keyword_hits"] or 0,
                )
                for r in rows
            ],
        )


class TopicStateCount(BaseModel):
    state_code: str
    state: Optional[str] = None
    # Distinct meetings (videos) in the state whose transcript matched the topic.
    meetings: int


class TopicStates(BaseModel):
    topic_id: int
    # Distinct meetings in scope (all states, or the one state asked for).
    total_meetings: int
    states: List[TopicStateCount]
    # Each state's map quote with its verbatim passage (<mark>ed): a real public meeting, where the public took a side
    # when the state has one, newest first (#1230). Kept under its old name for the front end's contract.
    newest: List[TopicMeeting]


_TOPIC_STATES_SQL = """
    SELECT l.state_code, max(l.state) AS state, count(DISTINCT l.video_id) AS meetings
    FROM topic_transcript_link l
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
    GROUP BY l.state_code
    ORDER BY meetings DESC, l.state_code
"""

# Each state's map quote (#1230). Only real public meetings: a video Jev read as `government_other` (media briefing,
# ceremony, interview) or `not_government` (podcast, stream) is never quoted (meeting_video_kind); an unscreened video
# is kept. Then meetings where the public took a side in the AI reading (topic_meeting_lean: mostly_opposed,
# mostly_supportive or mixed), newest first; only when a state has none, its other meetings, screened meetings first,
# newest first. The passage is the stored verbatim excerpt with the matched words in <mark>.
_TOPIC_NEWEST_PER_STATE_SQL = """
    SELECT DISTINCT ON (l.state_code)
           l.topic_transcript_link_id, l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
           l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits,
           CASE
               WHEN tml.public_lean IS NULL THEN NULL
               WHEN tml.public_lean = 'did_not_speak' THEN 'silent'
               WHEN tml.public_against THEN 'against'
               WHEN tml.public_for THEN 'for'
               ELSE 'split'
           END AS public_stance
    FROM topic_transcript_link l
    LEFT JOIN topic_meeting_lean tml ON tml.video_id = l.video_id AND tml.topic_id = l.topic_id
    LEFT JOIN meeting_video_kind k ON k.video_id = l.video_id
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL AND l.evidence_passage IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
      AND k.is_public_meeting IS NOT FALSE
    ORDER BY l.state_code,
             CASE
                 WHEN tml.public_lean IN ('mostly_opposed', 'mostly_supportive', 'mixed') THEN 0
                 WHEN k.is_public_meeting THEN 1
                 ELSE 2
             END,
             l.event_date DESC NULLS LAST, l.n_keyword_hits DESC, l.video_id
"""

# The pre-#1230 pick, for a serving copy that hasn't published meeting_video_kind / topic_meeting_lean yet: the newest
# passage per state. Never a 500 over a missing relation.
_TOPIC_NEWEST_PER_STATE_FALLBACK_SQL = """
    SELECT DISTINCT ON (l.state_code)
           l.topic_transcript_link_id, l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
           l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits,
           NULL::text AS public_stance
    FROM topic_transcript_link l
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL AND l.evidence_passage IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
    ORDER BY l.state_code, l.event_date DESC NULLS LAST, l.n_keyword_hits DESC
"""


_PASSAGE_SPEAKER_SQL = """
    SELECT s.topic_transcript_link_id, s.speaker_kind, s.speaker_display_name, s.speaker_role
    FROM meeting_passage_speaker s
    WHERE s.topic_transcript_link_id = ANY($1::text[]) AND s.speaker_display_name IS NOT NULL
      AND s.attribution_tier <> 'low'
"""


def speaker_fields(row: Optional[Any]) -> tuple[Optional[str], Optional[str]]:
    """(speaker_display_name, speaker_role) from a meeting_passage_speaker row (#1231). A resident's name is cut to
    "First L." again here (AGENTS.md, Privacy), whatever the table holds; officials keep their name and title."""
    if not row:
        return None, None
    name = " ".join(str(row.get("speaker_display_name") or "").split()) or None
    if name and row.get("speaker_kind") != "official":
        parts = name.split(" ")
        if len(parts) > 1 and not (len(parts) == 2 and len(parts[1]) == 2 and parts[1].endswith(".")):
            last = next((ch for ch in parts[-1] if ch.isalpha()), None)
            name = f"{parts[0]} {last.upper()}." if last else parts[0]
    if not name:
        return None, None
    return name, (row.get("speaker_role") or None)


async def _passage_speakers(conn: Any, link_ids: List[str]) -> dict[str, dict[str, Any]]:
    """meeting_passage_speaker rows keyed by topic_transcript_link_id, or {} when the table isn't in this database."""
    if not link_ids:
        return {}
    try:
        rows = await conn.fetch(_PASSAGE_SPEAKER_SQL, link_ids)
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("topic states: meeting_passage_speaker unavailable ({}); speakers null", e)
        return {}
    return {str(r["topic_transcript_link_id"]): dict(r) for r in rows}


# Up to `quotes_per_state` distinct real public meetings per state (#1357): one passage per video, stance meetings first,
# round-robin across public_stance so a state with multiple stance bands supplies a matching passage for each band.
_TOPIC_QUOTES_PER_STATE_SQL = """
    WITH per_video AS (
        SELECT DISTINCT ON (l.state_code, l.video_id)
               l.topic_transcript_link_id, l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
               l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits,
               CASE
                   WHEN tml.public_lean IS NULL THEN NULL
                   WHEN tml.public_lean = 'did_not_speak' THEN 'silent'
                   WHEN tml.public_against THEN 'against'
                   WHEN tml.public_for THEN 'for'
                   ELSE 'split'
               END AS public_stance,
               CASE
                   WHEN tml.public_lean IN ('mostly_opposed', 'mostly_supportive', 'mixed') THEN 0
                   WHEN k.is_public_meeting THEN 1
                   ELSE 2
               END AS tier
        FROM topic_transcript_link l
        LEFT JOIN topic_meeting_lean tml ON tml.video_id = l.video_id AND tml.topic_id = l.topic_id
        LEFT JOIN meeting_video_kind k ON k.video_id = l.video_id
        WHERE l.topic_id = $1 AND l.state_code IS NOT NULL AND l.evidence_passage IS NOT NULL
          AND ($2::text IS NULL OR l.state_code = $2::text)
          AND k.is_public_meeting IS NOT FALSE
        ORDER BY l.state_code, l.video_id, l.n_keyword_hits DESC, l.topic_transcript_link_id
    ),
    by_stance AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY state_code, COALESCE(public_stance, '')
                   ORDER BY tier, event_date DESC NULLS LAST, n_keyword_hits DESC, video_id
               ) AS stance_rn
        FROM per_video
    ),
    ranked AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY state_code
                   ORDER BY tier, stance_rn, event_date DESC NULLS LAST, n_keyword_hits DESC, video_id
               ) AS state_rn
        FROM by_stance
    )
    SELECT topic_transcript_link_id, video_id, event_title, event_date, state_code, state, city,
           jurisdiction_name, video_url, evidence_passage, n_keyword_hits, public_stance
    FROM ranked
    WHERE state_rn <= $3
    ORDER BY state_code, state_rn
"""

_TOPIC_QUOTES_PER_STATE_FALLBACK_SQL = """
    WITH per_video AS (
        SELECT DISTINCT ON (l.state_code, l.video_id)
               l.topic_transcript_link_id, l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
               l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits,
               NULL::text AS public_stance
        FROM topic_transcript_link l
        WHERE l.topic_id = $1 AND l.state_code IS NOT NULL AND l.evidence_passage IS NOT NULL
          AND ($2::text IS NULL OR l.state_code = $2::text)
        ORDER BY l.state_code, l.video_id, l.n_keyword_hits DESC, l.topic_transcript_link_id
    ),
    ranked AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY state_code
                   ORDER BY event_date DESC NULLS LAST, n_keyword_hits DESC, video_id
               ) AS state_rn
        FROM per_video
    )
    SELECT topic_transcript_link_id, video_id, event_title, event_date, state_code, state, city,
           jurisdiction_name, video_url, evidence_passage, n_keyword_hits, public_stance
    FROM ranked
    WHERE state_rn <= $3
    ORDER BY state_code, state_rn
"""


async def fetch_newest_per_state(
    conn: Any, topic_id: int, state_code: Optional[str], quotes_per_state: int = 1
) -> List[Any]:
    """Each state's map quote(s): real meetings, stance meetings first (#1230, #1357); the plain newest where the
    serving copy lacks the tables that rule needs."""
    if quotes_per_state > 1:
        try:
            return list(await conn.fetch(_TOPIC_QUOTES_PER_STATE_SQL, topic_id, state_code, quotes_per_state))
        except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as e:
            logger.warning("topic states: stance/meeting-kind tables unavailable ({}); newest passages per state", e)
            return list(await conn.fetch(_TOPIC_QUOTES_PER_STATE_FALLBACK_SQL, topic_id, state_code, quotes_per_state))
    try:
        return list(await conn.fetch(_TOPIC_NEWEST_PER_STATE_SQL, topic_id, state_code))
    except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as e:
        logger.warning("topic states: stance/meeting-kind tables unavailable ({}); newest passage per state", e)
        return list(await conn.fetch(_TOPIC_NEWEST_PER_STATE_FALLBACK_SQL, topic_id, state_code))


class TopicStanceStateCount(BaseModel):
    """One state's meetings and the AI reading of them (#1127). The counts are distinct meetings in
    ``topic_meeting_lean`` (#1126), never counted speakers; 0 where the state has no reading."""

    state_code: str
    state: Optional[str] = None
    # Distinct meetings in the state whose transcript matched the topic (topic_transcript_link).
    meetings: int
    # Meetings the AI read for this topic in the state.
    lean_meetings: int = 0
    public_against_meetings: int = 0
    public_for_meetings: int = 0
    # Read as split (#1200): the public spoke but neither confidently supported nor opposed (mixed, or a lean under
    # P 0.7). A label outside the question's choices is in none of the four counts.
    no_side_meetings: int = 0
    # Read, but the public didn't speak on the topic (#1200): shown as missing, never as split.
    silent_meetings: int = 0
    # The public mostly opposed while officials mostly supported it (same rule as data centers).
    disagreement_meetings: int = 0


class TopicStanceMap(BaseModel):
    topic_id: int
    # False when topic_meeting_lean isn't in this database yet or has no row for the topic: the map shows
    # meetings only and says so. Never a 0 that would read as "the public took no side anywhere".
    available: bool
    by_state: List[TopicStanceStateCount]


_TOPIC_LEAN_BY_STATE_SQL = """
    SELECT l.state_code,
           count(*)::int AS lean_meetings,
           count(*) FILTER (WHERE l.public_against)::int AS public_against_meetings,
           count(*) FILTER (WHERE l.public_for)::int AS public_for_meetings,
           count(*) FILTER (WHERE l.public_lean = 'did_not_speak')::int AS silent_meetings,
           count(*) FILTER (
               WHERE l.public_lean = 'mixed'
                  OR (l.public_lean IN ('mostly_opposed', 'mostly_supportive') AND coalesce(l.public_lean_p, 0) < 0.7)
           )::int AS no_side_meetings,
           count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings
    FROM topic_meeting_lean l
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
    GROUP BY l.state_code
"""


def merge_stance_by_state(
    counts: List[Any], lean: Optional[List[Any]]
) -> tuple[bool, List[TopicStanceStateCount]]:
    """Meetings per state with each state's AI-reading counts. ``lean`` is None when the table can't be read."""
    lean_by = {r["state_code"]: r for r in (lean or [])}
    out: List[TopicStanceStateCount] = []
    for r in counts:
        lr = lean_by.get(r["state_code"])
        read = int(lr["lean_meetings"]) if lr else 0
        against = int(lr["public_against_meetings"]) if lr else 0
        for_ = int(lr["public_for_meetings"]) if lr else 0
        silent = int(lr["silent_meetings"]) if lr else 0
        split = int(lr["no_side_meetings"]) if lr else 0
        out.append(
            TopicStanceStateCount(
                state_code=r["state_code"],
                state=r["state"],
                meetings=int(r["meetings"]),
                lean_meetings=read,
                public_against_meetings=against,
                public_for_meetings=for_,
                no_side_meetings=split,
                silent_meetings=silent,
                disagreement_meetings=int(lr["disagreement_meetings"]) if lr else 0,
            )
        )
    return bool(lean), out


@router.get("/{topic_id}/state-map", response_model=TopicStanceMap)
async def topic_state_map(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
) -> TopicStanceMap:
    """Meetings per state for a topic story's box map, with the AI reading of those meetings (#1127): how many the
    public mostly opposed, mostly supported or was split on, from ``topic_meeting_lean`` (#1126). Until that table has the
    topic, ``available`` is false and the map shows meetings only."""
    with tracer.start_as_current_span("topic-state-map") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                counts = await conn.fetch(_TOPIC_STATES_SQL, topic_id, state_code)
                try:
                    lean: Optional[List[Any]] = list(await conn.fetch(_TOPIC_LEAN_BY_STATE_SQL, topic_id, state_code))
                except asyncpg.exceptions.PostgresError as e:
                    # Not built yet (#1126) or a column is missing: meetings only, never a 500.
                    logger.warning("topic state-map: topic_meeting_lean unavailable ({}); meetings only", e)
                    lean = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic state-map failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's map is unavailable right now.") from exc
        available, by_state = merge_stance_by_state(list(counts), lean)
        span.set_attribute("topics.lean_available", available)
        return TopicStanceMap(topic_id=topic_id, available=available, by_state=by_state)


class TopicPlaceCount(BaseModel):
    """One government's meetings on a topic in the scoped state (#1349), in the shape of the data-center map's
    ``counts.by_place`` so ``StoryCountyMap`` reads both. The ``speakers_*`` fields carry MEETINGS as the AI read them
    (public mostly opposed, mostly supported, split), as the state map's ``topicStanceForMap`` does: never counted
    speakers. 0 where the government has no reading."""

    jurisdiction_id: str
    jurisdiction_name: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    geoid: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    meetings: int
    lean_meetings: int = 0
    speakers_against: int = 0
    speakers_for: int = 0
    speakers_neutral: int = 0
    speakers_question: int = 0
    silent_meetings: int = 0
    # Public-against is already a band above; only the officials-against-the-public count is carried as a lean.
    public_against_meetings: int = 0
    disagreement_meetings: int = 0


class TopicPlaces(BaseModel):
    topic_id: int
    state_code: str
    # Distinct meetings on the topic in the state (topic_transcript_link): the same count as /states for the state.
    total_meetings: int
    # Meetings whose government can't be drawn (not in jurisdictions, filed under another state, or no county geoid or
    # coordinates): total_meetings minus the sum of by_place.meetings. The map footnotes them.
    unplaced_meetings: int
    # False when topic_place_meeting isn't in this database yet: the page keeps the state outline.
    available: bool
    by_place: List[TopicPlaceCount]


_TOPIC_PLACES_SQL = """
    SELECT p.jurisdiction_id, p.jurisdiction_name, p.jurisdiction_type, p.geoid, p.latitude, p.longitude,
           p.meetings, p.lean_meetings, p.public_against_meetings, p.public_for_meetings, p.no_side_meetings,
           p.silent_meetings, p.disagreement_meetings
    FROM topic_place_meeting p
    WHERE p.topic_id = $1 AND p.state_code = $2
    ORDER BY p.meetings DESC, p.jurisdiction_id
"""

_TOPIC_STATE_TOTAL_SQL = """
    SELECT count(DISTINCT l.video_id)::int FROM topic_transcript_link l
    WHERE l.topic_id = $1 AND l.state_code = $2
"""


def shape_topic_places(topic_id: int, state_code: str, total: int, rows: Optional[List[Any]]) -> TopicPlaces:
    """Per-government counts and the unplaced remainder. ``rows`` is None when the mart can't be read."""
    if rows is None:
        return TopicPlaces(
            topic_id=topic_id, state_code=state_code, total_meetings=total, unplaced_meetings=total, available=False, by_place=[]
        )
    places = [
        TopicPlaceCount(
            jurisdiction_id=str(r["jurisdiction_id"]),
            jurisdiction_name=r["jurisdiction_name"],
            jurisdiction_type=r["jurisdiction_type"],
            geoid=r["geoid"],
            latitude=float(r["latitude"]) if r["latitude"] is not None else None,
            longitude=float(r["longitude"]) if r["longitude"] is not None else None,
            meetings=int(r["meetings"] or 0),
            lean_meetings=int(r["lean_meetings"] or 0),
            speakers_against=int(r["public_against_meetings"] or 0),
            speakers_for=int(r["public_for_meetings"] or 0),
            speakers_neutral=int(r["no_side_meetings"] or 0),
            silent_meetings=int(r["silent_meetings"] or 0),
            disagreement_meetings=int(r["disagreement_meetings"] or 0),
        )
        for r in rows
        if int(r["meetings"] or 0) > 0
    ]
    placed = sum(p.meetings for p in places)
    return TopicPlaces(
        topic_id=topic_id,
        state_code=state_code,
        total_meetings=total,
        unplaced_meetings=max(0, total - placed),
        available=True,
        by_place=places,
    )


@router.get("/{topic_id}/places", response_model=TopicPlaces)
async def topic_places(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: str = Query(..., min_length=2, max_length=2, description="2-letter state code (required: the county map is per state)."),
) -> TopicPlaces:
    """Meetings per government in one state for a topic story's county map (#1349): each government's geoid and
    coordinates (a county is drawn by its geoid; a city, town or school district is placed in the county its point falls
    in), with the AI reading of its meetings. Counts are distinct meetings from ``topic_place_meeting``; meetings that
    can't be placed are reported as ``unplaced_meetings``, never spread or guessed."""
    with tracer.start_as_current_span("topic-places") as span:
        state_code = state.strip().upper()
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                total = int(await conn.fetchval(_TOPIC_STATE_TOTAL_SQL, topic_id, state_code) or 0)
                try:
                    rows: Optional[List[Any]] = list(await conn.fetch(_TOPIC_PLACES_SQL, topic_id, state_code))
                except asyncpg.exceptions.PostgresError as e:
                    # Not published yet (#1349): the page keeps the state outline, never a 500.
                    logger.warning("topic places: topic_place_meeting unavailable ({}); outline only", e)
                    rows = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic places failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's county map is unavailable right now.") from exc
        out = shape_topic_places(topic_id, state_code, total, rows)
        span.set_attribute("topics.places", len(out.by_place))
        span.set_attribute("topics.unplaced", out.unplaced_meetings)
        return out


@router.get("/{topic_id}/states", response_model=TopicStates)
async def topic_states(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
    quotes_per_state: int = Query(1, ge=1, le=6, description="Max distinct meeting passages returned per state (1..6)."),
) -> TopicStates:
    """Meetings per state for a curated topic, and each state's newest matched passage(s) (#1013, #1357): the data
    behind a topic story's map and headline. Counts are distinct meetings; nothing is estimated."""
    with tracer.start_as_current_span("topic-states") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.quotes_per_state", quotes_per_state)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                counts = await conn.fetch(_TOPIC_STATES_SQL, topic_id, state_code)
                newest = await fetch_newest_per_state(conn, topic_id, state_code, quotes_per_state)
                speakers = await _passage_speakers(
                    conn, [str(r["topic_transcript_link_id"]) for r in newest if r.get("topic_transcript_link_id")]
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic states failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's map is unavailable right now.") from exc
        states = [TopicStateCount(state_code=r["state_code"], state=r["state"], meetings=int(r["meetings"])) for r in counts]
        span.set_attribute("topics.states", len(states))
        span.set_attribute("topics.newest_with_speaker", len(speakers))
        return TopicStates(
            topic_id=topic_id,
            total_meetings=sum(s.meetings for s in states),
            states=states,
            newest=[
                TopicMeeting(
                    video_id=r["video_id"],
                    title=r["event_title"],
                    date=r["event_date"].isoformat() if r["event_date"] else None,
                    state_code=r["state_code"],
                    state=r["state"],
                    city=r["city"],
                    jurisdiction_name=r["jurisdiction_name"],
                    video_url=r["video_url"],
                    excerpt=r["evidence_passage"],
                    n_keyword_hits=r["n_keyword_hits"] or 0,
                    speaker_display_name=speaker_fields(speakers.get(str(r.get("topic_transcript_link_id"))))[0],
                    speaker_role=speaker_fields(speakers.get(str(r.get("topic_transcript_link_id"))))[1],
                    public_stance=r["public_stance"],
                )
                for r in newest
            ],
        )


# --- Decisions: on the topic or in passing (#1293) ------------------------------------------------------------------------


class TopicDecision(DecisionPeople):
    """One decision whose headline or statement matched the topic's keywords, with where it was taken and why it is (or
    isn't) counted as a decision on the topic."""

    event_decision_id: str
    title: str
    # The matched passage of the headline and statement, terms in <mark>…</mark> (render with highlightSnippet).
    excerpt: Optional[str] = None
    outcome: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    state_code: Optional[str] = None
    state: Optional[str] = None
    meeting_name: Optional[str] = None
    # ISO yyyy-mm-dd or None.
    meeting_date: Optional[str] = None
    # The decision's page (/decisions/{id}).
    decision_url: str
    # The meeting's page in the app (/meetings/{event_meeting_id}), or None.
    meeting_url: Optional[str] = None
    # The recording (YouTube). Decisions carry no timestamp, so it opens at the start.
    video_url: Optional[str] = None
    video_id: Optional[str] = None
    relevance: Literal["on_topic", "in_passing"]
    # Which rule decided (api/routes/topic_relevance.py); for audit, never shown as a quote.
    relevance_basis: str


class TopicDecisionList(BaseModel):
    topic_id: int
    topic_slug: Optional[str] = None
    # Every decision in scope whose text matched the topic, and the split of them.
    total: int = 0
    on_topic_total: int = 0
    in_passing_total: int = 0
    # Newest first, at most `limit` of each.
    on_topic: List[TopicDecision] = []
    in_passing: List[TopicDecision] = []


_TOPIC_DECISIONS_SQL = """
    SELECT d.event_decision_id, d.headline, d.decision_statement, d.outcome, d.jurisdiction_name, d.state_code, d.state,
           d.jurisdiction_type, d.competing_views::text AS competing_views, d.vote_tally::text AS vote_tally,
           (SELECT ds.speaker_ids::text FROM decision_speakers ds WHERE ds.event_decision_id = d.event_decision_id) AS speaker_ids,
           m.event_meeting_id, m.body_name, m.video_id,
           CASE WHEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                THEN left(COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')), 10) END AS meeting_date,
           ts_headline('english', concat_ws('. ', NULLIF(d.headline, ''), NULLIF(d.decision_statement, '')),
                       to_tsquery('english', $1),
                       'MaxFragments=2, MinWords=5, MaxWords=18, StartSel=<mark>, StopSel=</mark>') AS excerpt
    FROM event_decision d
    LEFT JOIN LATERAL (
        SELECT e.event_meeting_id, e.body_name, e.video_id, e.event_date, e.meeting_date FROM event_meeting e
        WHERE e.c1_event_id = d.c1_event_id ORDER BY e.event_meeting_id LIMIT 1
    ) m ON TRUE
    WHERE d.search_tsv @@ to_tsquery('english', $1)
      AND ($2::text IS NULL OR d.state_code = $2::text)
      AND ($3::text IS NULL OR d.city ILIKE $3::text OR d.jurisdiction_name ILIKE $3::text)
    ORDER BY meeting_date DESC NULLS LAST, d.event_decision_id DESC
    LIMIT 2000
"""

_DECISION_LEAN_SQL = """
    SELECT t.video_id,
           CASE
               WHEN t.public_lean IS NULL OR coalesce(t.excluded_no_item, false) OR t.public_lean = 'did_not_speak' THEN NULL
               WHEN t.public_against THEN 'against'
               WHEN t.public_for THEN 'for'
               WHEN t.public_lean IN ('mixed', 'mostly_opposed', 'mostly_supportive') THEN 'split'
           END AS public_stance,
           CASE WHEN NOT coalesce(t.excluded_no_item, false) THEN t.outcome_group END AS vote
    FROM topic_meeting_lean t WHERE t.topic_id = $1 AND t.video_id = ANY($2::text[])
"""


def youtube_url(video_id: Optional[str]) -> Optional[str]:
    """The recording on YouTube for an 11-character video id; None for anything else."""
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return f"https://www.youtube.com/watch?v={video_id}"
    return None


def decision_people_fields(r: dict[str, Any], officials: Any = None) -> dict[str, Any]:
    """The decision's people and vote (#1320); see api/routes/decision_people.py."""
    from api.routes.decision_people import people_fields

    return people_fields(r, officials)


def shape_topic_decisions(
    topic_id: int, slug: Optional[str], rows: List[Any], lean: dict[str, dict[str, Any]], limit: int, officials: Any = None
) -> TopicDecisionList:
    """Classify every decision in scope (topic_relevance) and keep the newest `limit` of each group."""
    from api.routes.topic_relevance import classify_decision

    on: List[TopicDecision] = []
    passing: List[TopicDecision] = []
    n_on = n_pass = 0
    for r in rows:
        reading = lean.get(str(r.get("video_id") or "")) or {}
        rel, basis = classify_decision(
            slug, r.get("headline"), r.get("decision_statement"),
            public_stance=reading.get("public_stance"), vote=reading.get("vote"),
        )
        if rel == "on_topic":
            n_on += 1
            bucket, room = on, len(on) < limit
        else:
            n_pass += 1
            bucket, room = passing, len(passing) < limit
        if not room:
            continue
        title = (r.get("headline") or r.get("decision_statement") or "Untitled decision").strip()
        emid = r.get("event_meeting_id")
        bucket.append(
            TopicDecision(
                event_decision_id=str(r["event_decision_id"]),
                title=title[:150] + ("…" if len(title) > 150 else ""),
                excerpt=r.get("excerpt"),
                outcome=r.get("outcome"),
                jurisdiction_name=r.get("jurisdiction_name"),
                state_code=r.get("state_code"),
                state=r.get("state"),
                meeting_name=r.get("body_name"),
                meeting_date=r.get("meeting_date"),
                decision_url=f"/decisions/{r['event_decision_id']}",
                meeting_url=f"/meetings/{emid}" if emid is not None else None,
                video_url=youtube_url(r.get("video_id")),
                video_id=r.get("video_id") if youtube_url(r.get("video_id")) else None,
                relevance=rel,
                relevance_basis=basis,
                **decision_people_fields(r, officials),
            )
        )
    return TopicDecisionList(
        topic_id=topic_id, topic_slug=slug, total=n_on + n_pass, on_topic_total=n_on, in_passing_total=n_pass,
        on_topic=on, in_passing=passing,
    )


@router.get("/{topic_id}/decisions", response_model=TopicDecisionList)
async def list_topic_decisions(
    topic_id: int = Path(..., description="Topic id."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
    city: Optional[str] = Query(None, description="Optional city / jurisdiction name (ILIKE)."),
    limit: int = Query(12, ge=1, le=60, description="Decisions listed per group (1..60); the totals are the scope's."),
) -> TopicDecisionList:
    """Decisions whose headline or statement matched the topic's keywords, split into decisions on the topic and ones
    that only mention it (api/routes/topic_relevance.py: deterministic rules and the meeting's AI reading; no model
    call). An unclassifiable decision is "in passing", never on the topic. Each links its meeting and its page."""
    from api.routes.search import resolve_topic_tsquery

    with tracer.start_as_current_span("topic-decisions") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        city_like = f"%{city.strip()}%" if city and city.strip() and state_code else None
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        tsq = await resolve_topic_tsquery(topic_id)
        if not tsq:
            return TopicDecisionList(topic_id=topic_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                slug = await conn.fetchval("SELECT query_id FROM civicsearch_topic WHERE topic_id = $1", topic_id)
                rows = [dict(r) for r in await conn.fetch(_TOPIC_DECISIONS_SQL, tsq, state_code, city_like)]
                videos = sorted({str(r["video_id"]) for r in rows if r.get("video_id")})
                from api.routes.decision_people import load_officials

                officials = await load_officials(conn, {(r.get("state_code"), r.get("jurisdiction_name")) for r in rows})
                lean: dict[str, dict[str, Any]] = {}
                if videos:
                    try:
                        lean = {str(r["video_id"]): dict(r) for r in await conn.fetch(_DECISION_LEAN_SQL, topic_id, videos)}
                    except asyncpg.exceptions.PostgresError as e:
                        logger.warning("topic decisions: topic_meeting_lean unavailable ({}); rules only", e)
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic decisions failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Decisions for this topic are unavailable right now.") from exc
        out = shape_topic_decisions(topic_id, slug, rows, lean, limit, officials)
        span.set_attribute("topics.decisions_total", out.total)
        span.set_attribute("topics.decisions_on_topic", out.on_topic_total)
        return out
