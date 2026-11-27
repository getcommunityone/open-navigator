"""How the public and elected officials leaned on a topic, per meeting, read by Jev (#1126).

The data-center screen (#1113) asks Jev how members of the public and the elected officials leaned on a large data
center. This module asks the same three questions for any topic in :data:`TOPICS`, with a careful per-topic definition
of what is being supported or opposed (and what doesn't count, so a staple gun is never a firearm):

- ``public_lean`` (Choice): mostly_supportive, mostly_opposed, mixed, did_not_speak;
- ``official_lean`` (Choice): the same labels, for the elected officials;
- ``outcome`` (Choice): advanced, blocked, tabled_or_deferred, discussed_no_action, no_item.

Every lean is an aggregate reading of one meeting, never tied to a person (AGENTS.md, Privacy). Jev returns
probabilities, not text.

Meetings come from ``public.topic_transcript_link`` (the curated keyword links) for the topic's ``topic_id``. Only the
transcript chunks that contain one of the topic's keywords are sent (up to ``--max-chunks``), so the rest of a long
meeting neither costs tokens nor drowns out the passage. Each answer is averaged only over the chunks where Jev judges
the public (or the officials, or an item) was on the topic, with :func:`public_lean`.

Results land in ``bronze.bronze_transcript_topic_lean_jev``, one row per (video_id, topic_id, question_version). A run
skips meetings already screened at the topic's current question version, so it can be stopped and resumed.

This is the version that wrote the stored readings (#1201, #1239): its question wording hashes to the
``question_version`` of every row in the table (pinned in ``tests/test_topic_lean.py``, ``STORED_QUESTION_VERSIONS``).
Rewording a topic changes its hash and re-reads all of that topic's meetings, at Jev's per-token price.

Usage (paid: run only on the owner's go-ahead for that run; read usage before and after, AGENTS.md)::

    python -m llm.typesafe.screen_transcripts --topic pickleball --limit 20 --dry-run
    python -m llm.typesafe.screen_transcripts --topic all --limit 100000 --dry-run
    python -m llm.typesafe.screen_transcripts --topic pickleball --limit 20
    python -m llm.typesafe.screen_transcripts --topic guns --limit 100000 --max-input-tokens 200000000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from llm.typesafe.client import JevClient, JevError, JevResponse, choice
from llm.typesafe.screen_transcripts import (
    _OFFICIALS,
    CHARS_PER_TOKEN,
    chunk_segments,
    pick_chunks,
    public_lean,
)
from llm.usage.calls import llm_call_context

TABLE = "bronze.bronze_transcript_topic_lean_jev"

LEAN_NONE = "did_not_speak"
OUTCOME_NONE = "no_item"

# Who counts as the public (#1113, widened for topics whose item is presented by police, a vendor or a department).
_PUBLIC = (
    "members of the public who spoke (residents, local business owners, advocacy groups, and doctors or other "
    "professionals speaking as residents), not elected officials, government staff, police or department heads "
    "presenting, consultants, or an applicant, vendor or company presenting the item"
)


@dataclass(frozen=True)
class TopicDef:
    """One topic's definition: what supporting or opposing means, and what doesn't count."""

    slug: str
    topic_id: int
    # The thing the public and officials are for or against, as a phrase.
    subject: str
    # A short name for the item, for the outcome labels ("pickleball courts").
    item: str
    # False hits to leave out (other senses of the keywords, passing mentions).
    excludes: str
    # Who is for and who is against, in plain examples.
    sides: str
    # The outcome that moves the subject forward, and the one that stops or limits it.
    advanced: str
    blocked: str
    # Optional topic-specific label sets (fluoridation mirrors CareQuest's national poll, #1126). ``None`` uses the
    # shared LEAN_LABELS / OUTCOME_LABELS wording built from ``subject``.
    public_labels: dict[str, str] | None = field(default=None, hash=False)
    official_labels: dict[str, str] | None = field(default=None, hash=False)
    outcome_labels: dict[str, str] | None = field(default=None, hash=False)
    outcome_none: str = "no_item"


# CareQuest Institute, "Attitudes about Fluoride: National Survey Results" (Marketing for Change Co., July 7-9, 2025,
# n=1,114, +/-2.94%), asked "Which of the following comes closest to your position?". The fluoridation leans use the
# same five answers (plus did_not_speak), read for the group that spoke at the meeting, so the story can chart the
# meetings beside the poll. dbt rolls support_* up to "for" and oppose_* up to "against" for the four-colour map.
_FLUORIDE_POSITIONS = {
    "support_require_all": (
        "support fluoridation and think all communities should be required to fluoridate (for example backing a state "
        "requirement, or saying every community should fluoridate)"
    ),
    "support_local_choice": (
        "support fluoridation and think each community should decide whether it wants to fluoridate (asking their own "
        "community to keep, start or restore fluoridation, without calling for a requirement everywhere, counts here)"
    ),
    "no_opinion": "take no side on fluoridation (they asked questions or said they had no opinion)",
    "oppose_local_choice": (
        "oppose fluoridation and think each community should decide (asking their own community to stop or not start "
        "fluoridating, without calling for a ban everywhere, counts here)"
    ),
    "oppose_ban_all": (
        "oppose fluoridation and think all communities should be banned from fluoridating (for example backing a state "
        "ban, or saying no community should fluoridate)"
    ),
}


def _positions(who: str, verb: str) -> dict[str, str]:
    labels = {k: f"Most of {who} who {verb} on community water fluoridation {v}" for k, v in _FLUORIDE_POSITIONS.items()}
    labels["did_not_speak"] = f"None of {who} took a position on community water fluoridation, or nobody discussed it"
    return labels


TOPICS: dict[str, TopicDef] = {
    "guns": TopicDef(
        slug="guns",
        topic_id=100005,
        subject=(
            "a local gun-control measure: an ordinance, resolution, policy or vote that limits firearms (where guns "
            "may be carried or fired, gun sales, gun shows, gun shops or shooting ranges near homes, safe storage, "
            "assault weapons or ghost guns)"
        ),
        item="gun-control measure",
        excludes=(
            "A tool or device called a gun (staple, nail, glue, caulk, spray, paint, radar or speed gun, starting "
            "pistol) is not a firearm. Police buying, carrying or qualifying with their own service weapons, a report "
            "of a shooting or crime where no limit on firearms is debated, and gunshot-detection technology such as "
            "ShotSpotter do not count."
        ),
        sides=(
            "People asking for limits on guns, or objecting to a shooting range, gun shop or gun show near homes, are "
            "for it. People defending gun rights, or backing a Second Amendment 'sanctuary' resolution, are against it."
        ),
        advanced=(
            "The body adopted or advanced a limit on firearms, including denying or restricting a shooting range, "
            "gun shop or gun show"
        ),
        blocked=(
            "The body rejected or repealed a limit on firearms, adopted a Second Amendment sanctuary resolution, or "
            "approved a shooting range, gun shop or gun show"
        ),
    ),
    "short-term-rentals": TopicDef(
        slug="short-term-rentals",
        topic_id=100003,
        subject=(
            "allowing short-term rentals: renting out homes or rooms for stays of less than about 30 days through "
            "Airbnb, VRBO or similar vacation rentals (permits for them, zoning that allows them, or looser limits)"
        ),
        item="short-term rental",
        excludes=(
            "Long-term apartment or house rentals, hotels, motels, RV parks or campgrounds, and renting equipment, "
            "venues or city facilities are not short-term rentals."
        ),
        sides=(
            "Neighbors complaining about short-term rentals' noise, parking or trash, or asking for a ban, a cap or a "
            "moratorium, are against them. Owners, hosts and property managers defending them are for them."
        ),
        advanced=(
            "The body approved a short-term rental permit or use, or adopted rules that allow or legalize short-term "
            "rentals (including a registration or permit system that lets them operate) or loosen limits on them"
        ),
        blocked=(
            "The body denied a short-term rental permit, or banned, capped, paused (moratorium) or tightened limits "
            "on short-term rentals"
        ),
    ),
    "pickleball": TopicDef(
        slug="pickleball",
        topic_id=100006,
        subject=(
            "pickleball courts and play: building, adding, converting (for example from tennis courts), lighting or "
            "keeping open pickleball courts, and the hours they are played"
        ),
        item="pickleball court",
        excludes=(
            "Pickles or food, tennis, basketball or other sports alone, and a passing mention of pickleball in a list "
            "of recreation programs or classes, with no debate about courts, noise, location or hours, do not count."
        ),
        sides=(
            "Neighbors complaining about pickleball noise, or objecting to where courts go, are against. Players "
            "asking for more courts, lights or hours are for."
        ),
        advanced=(
            "The body approved, funded or built pickleball courts, converted courts to pickleball, added lights or "
            "extended playing hours"
        ),
        blocked=(
            "The body denied, removed or closed pickleball courts, cut playing hours, or limited play because of noise"
        ),
    ),
    "license-plate-readers": TopicDef(
        slug="license-plate-readers",
        topic_id=100004,
        subject=(
            "a government's (usually the police's) use of automated license plate readers (ALPR cameras, including "
            "Flock Safety cameras): buying, installing, renewing, expanding or keeping them, and sharing their data"
        ),
        item="license plate reader",
        excludes=(
            "Red-light or speed cameras, ordinary security, traffic or body cameras, vehicle registration or license "
            "plates themselves, and a 'flock' of birds or a church's flock are not license plate readers."
        ),
        sides=(
            "Residents raising privacy, surveillance or data-sharing concerns (for example sharing with immigration "
            "authorities) are against. Residents asking for the cameras for safety or to solve crimes are for."
        ),
        advanced=(
            "The body approved a contract, purchase, installation, renewal or expansion of license plate readers or "
            "Flock cameras"
        ),
        blocked=(
            "The body rejected, cancelled, paused or removed license plate readers or Flock cameras, or adopted new "
            "limits on their use or data sharing"
        ),
    ),
    "water-fluoridation": TopicDef(
        slug="water-fluoridation",
        topic_id=100002,
        subject=(
            "community water fluoridation: adding fluoride to the public drinking water supply (starting, continuing, "
            "restoring or ending it)"
        ),
        item="fluoridation",
        excludes=(
            "Fluoride toothpaste, dental varnish or school dental programs alone, other water treatment chemicals "
            "(chlorine, PFAS 'forever chemicals', lead), and fluoride mentioned only in a routine water quality report "
            "do not count."
        ),
        sides=(
            "Pick the answer closest to the position most of the group who spoke took, as in the national poll "
            "question 'Which of the following comes closest to your position?'."
        ),
        advanced="The body voted to keep, start, restore or fund fluoridating the water supply",
        blocked="The body voted to stop, end or pause fluoridating the water supply",
        public_labels=_positions(
            "the members of the public who spoke (residents, local business owners, advocacy groups, and dentists, "
            "doctors or other professionals speaking as residents; not elected officials, staff or presenters)",
            "spoke",
        ),
        official_labels=_positions(
            "the elected officials (council, commission or board members), not staff and not the public,", "spoke or voted"
        ),
        outcome_labels={
            "voted_to_end_fluoridation": "The body voted to stop, end or pause fluoridating the water supply",
            "voted_to_keep_or_start": "The body voted to keep, start, restore or fund fluoridating the water supply",
            "tabled_or_deferred": (
                "A fluoridation item was tabled, deferred, continued, sent to a referendum or postponed to a later "
                "meeting"
            ),
            "discussion_only": "Fluoridation was discussed, but no vote or action on it was taken",
            "no_fluoridation_item": "No fluoridation item came up in this part of the meeting",
        },
        outcome_none="no_fluoridation_item",
    ),
}

# The lean and outcome labels every topic shares (the mart reads these names).
LEAN_LABELS: tuple[str, ...] = ("mostly_supportive", "mostly_opposed", "mixed", LEAN_NONE)
OUTCOME_LABELS: tuple[str, ...] = ("advanced", "blocked", "tabled_or_deferred", "discussed_no_action", OUTCOME_NONE)


def topic_questions(topic: TopicDef) -> dict[str, dict[str, Any]]:
    """The three Jev questions for one topic."""
    about = f"{topic.subject}. {topic.excludes} {topic.sides}"
    public = {
        "mostly_supportive": f"During public comment, most of the {_PUBLIC} who spoke on it were for {topic.subject}",
        "mostly_opposed": f"During public comment, most of the {_PUBLIC} who spoke on it were against {topic.subject}",
        "mixed": f"During public comment, some of the {_PUBLIC} spoke for and others against {topic.subject}",
        LEAN_NONE: (
            f"None of the {_PUBLIC} spoke for or against {topic.subject}; only officials, staff or presenters "
            "discussed it, or nobody did"
        ),
    }
    officials = {
        "mostly_supportive": f"Most of {_OFFICIALS} who spoke or voted on it were for {topic.subject}",
        "mostly_opposed": f"Most of {_OFFICIALS} who spoke or voted on it were against {topic.subject}",
        "mixed": f"Some of {_OFFICIALS} spoke or voted for and others against {topic.subject}",
        LEAN_NONE: f"None of {_OFFICIALS} took a position for or against {topic.subject}",
    }
    outcomes = {
        "advanced": topic.advanced,
        "blocked": topic.blocked,
        "tabled_or_deferred": (
            f"A {topic.item} item was tabled, deferred, continued, sent to a referendum or postponed to a later meeting"
        ),
        "discussed_no_action": f"A {topic.item} item was discussed, but no vote or action on it was taken",
        OUTCOME_NONE: f"No {topic.item} item came up in this part of the meeting",
    }
    return {
        "public_lean": choice(f"How the {_PUBLIC} leaned on {about}", topic.public_labels or public),
        "official_lean": choice(f"How {_OFFICIALS} leaned on {about}", topic.official_labels or officials),
        "outcome": choice(f"What the body did about {about}", topic.outcome_labels or outcomes),
    }


def question_version(topic: TopicDef) -> str:
    """Changes whenever a topic's question wording changes, so a rewording is screened again."""
    return hashlib.sha256(json.dumps(topic_questions(topic), sort_keys=True).encode()).hexdigest()[:12]


CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    video_id                     text NOT NULL,
    topic_id                     integer NOT NULL,
    question_version             text NOT NULL,
    topic_slug                   text NOT NULL,
    model                        text NOT NULL,
    public_lean                  text,
    public_lean_probabilities    jsonb,
    official_lean                text,
    official_lean_probabilities  jsonb,
    outcome                      text,
    outcome_probabilities        jsonb,
    chunk_count                  integer NOT NULL,
    chunks_screened              integer NOT NULL,
    keyword_chunks               integer NOT NULL,
    chunk_selection              text,
    passages_covered             integer,
    transcript_chars             integer NOT NULL,
    input_tokens                 integer,
    answers                      jsonb NOT NULL,
    screened_at                  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, topic_id, question_version)
)
"""

# #1145 audit columns, for tables created before them. Rows screened before the columns existed are backfilled from
# keyword_chunks / chunks_screened: with keyword selection every screened chunk holds a keyword passage.
ALTER_SQL = f"""
ALTER TABLE {TABLE}
    ADD COLUMN IF NOT EXISTS chunk_selection text,
    ADD COLUMN IF NOT EXISTS passages_covered integer;
UPDATE {TABLE}
SET chunk_selection = CASE WHEN keyword_chunks > 0 THEN 'keyword_passages' ELSE 'evenly_spaced' END,
    passages_covered = CASE WHEN keyword_chunks > 0 THEN chunks_screened ELSE 0 END
WHERE chunk_selection IS NULL
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE} (
    video_id, topic_id, question_version, topic_slug, model,
    public_lean, public_lean_probabilities, official_lean, official_lean_probabilities,
    outcome, outcome_probabilities, chunk_count, chunks_screened, keyword_chunks, chunk_selection, passages_covered,
    transcript_chars, input_tokens, answers, screened_at
) VALUES (
    %(video_id)s, %(topic_id)s, %(question_version)s, %(topic_slug)s, %(model)s,
    %(public_lean)s, %(public_lean_probabilities)s, %(official_lean)s, %(official_lean_probabilities)s,
    %(outcome)s, %(outcome_probabilities)s, %(chunk_count)s, %(chunks_screened)s, %(keyword_chunks)s,
    %(chunk_selection)s, %(passages_covered)s,
    %(transcript_chars)s, %(input_tokens)s, %(answers)s, %(screened_at)s
)
ON CONFLICT (video_id, topic_id, question_version) DO UPDATE SET
    topic_slug = EXCLUDED.topic_slug,
    model = EXCLUDED.model,
    public_lean = EXCLUDED.public_lean,
    public_lean_probabilities = EXCLUDED.public_lean_probabilities,
    official_lean = EXCLUDED.official_lean,
    official_lean_probabilities = EXCLUDED.official_lean_probabilities,
    outcome = EXCLUDED.outcome,
    outcome_probabilities = EXCLUDED.outcome_probabilities,
    chunk_count = EXCLUDED.chunk_count,
    chunks_screened = EXCLUDED.chunks_screened,
    keyword_chunks = EXCLUDED.keyword_chunks,
    chunk_selection = EXCLUDED.chunk_selection,
    passages_covered = EXCLUDED.passages_covered,
    transcript_chars = EXCLUDED.transcript_chars,
    input_tokens = EXCLUDED.input_tokens,
    answers = EXCLUDED.answers,
    screened_at = EXCLUDED.screened_at
"""


@dataclass(frozen=True)
class TopicLeanResult:
    """One meeting's reading on one topic, ready to write."""

    video_id: str
    topic: TopicDef
    model: str
    public_lean: str | None
    public_lean_probabilities: dict[str, float] | None
    official_lean: str | None
    official_lean_probabilities: dict[str, float] | None
    outcome: str | None
    outcome_probabilities: dict[str, float] | None
    chunk_count: int
    chunks_screened: int
    keyword_chunks: int
    transcript_chars: int
    input_tokens: int | None
    answers: list[dict[str, Any]]
    # #1145: how the chunks were chosen, and how many keyword-passage chunks were screened (of keyword_chunks).
    chunk_selection: str = "keyword_passages"
    passages_covered: int = 0

    def row(self, *, screened_at: datetime | None = None) -> dict[str, Any]:
        def _j(value: Any) -> str | None:
            return json.dumps(value) if value is not None else None

        return {
            "video_id": self.video_id,
            "topic_id": self.topic.topic_id,
            "question_version": question_version(self.topic),
            "topic_slug": self.topic.slug,
            "model": self.model,
            "public_lean": self.public_lean,
            "public_lean_probabilities": _j(self.public_lean_probabilities),
            "official_lean": self.official_lean,
            "official_lean_probabilities": _j(self.official_lean_probabilities),
            "outcome": self.outcome,
            "outcome_probabilities": _j(self.outcome_probabilities),
            "chunk_count": self.chunk_count,
            "chunks_screened": self.chunks_screened,
            "keyword_chunks": self.keyword_chunks,
            "chunk_selection": self.chunk_selection,
            "passages_covered": self.passages_covered,
            "transcript_chars": self.transcript_chars,
            "input_tokens": self.input_tokens,
            "answers": json.dumps(self.answers),
            "screened_at": screened_at or datetime.now(UTC),
        }


def keyword_pattern(keywords: Sequence[str]) -> re.Pattern[str] | None:
    """One case-insensitive pattern for the topic's keyword phrases. A space or hyphen matches either, and a word may
    run on (``firearm`` matches ``firearms``), like the stemmed phrase match that built the topic links."""
    parts = []
    for kw in keywords:
        words = [re.escape(w) for w in re.split(r"[\s-]+", str(kw).strip().lower()) if w]
        if words:
            parts.append(r"\b" + r"[\s-]+".join(words))
    if not parts:
        return None
    return re.compile("|".join(sorted(set(parts), key=len, reverse=True)), re.IGNORECASE)


def pick_keyword_chunks(
    chunks: Sequence[str], pattern: re.Pattern[str] | None, max_chunks: int, *, neighbors: int = 0
) -> tuple[list[int], int]:
    """The chunks to send: those with the most keyword hits (up to ``max_chunks``, in meeting order), plus
    ``neighbors`` chunks on each side of them, and how many chunks had a hit. With no hit anywhere, fall back to evenly
    spaced chunks (never only the head of the transcript, #1145)."""
    hits = [(len(pattern.findall(c)) if pattern else 0) for c in chunks]
    with_hits = [i for i, n in enumerate(hits) if n]
    if not with_hits:
        return pick_chunks(chunks, max_chunks), 0
    best = set(sorted(with_hits, key=lambda i: (-hits[i], i))[:max_chunks])
    for i in list(best):
        best.update(j for j in range(i - neighbors, i + neighbors + 1) if 0 <= j < len(chunks))
    return sorted(best), len(with_hits)


def chunk_coverage(
    chunks: Sequence[str], picked: Sequence[int], pattern: re.Pattern[str] | None, keyword_chunks: int
) -> tuple[str, int]:
    """(chunk_selection, passages_covered): how the chunks were chosen, and how many of the screened chunks hold a
    keyword passage (compare with keyword_chunks, the chunks that hold one at all) (#1145)."""
    if not keyword_chunks or pattern is None:
        return "evenly_spaced", 0
    return "keyword_passages", sum(1 for i in picked if pattern.search(chunks[i]))


def aggregate_topic(responses: Sequence[JevResponse], *, outcome_none: str = OUTCOME_NONE) -> dict[str, Any]:
    """Combine per-chunk answers: each lean over the chunks where that group spoke, the outcome over the chunks where
    an item came up (:func:`public_lean`)."""
    out: dict[str, Any] = {}
    out.update(public_lean(responses, key="public_lean", none_label=LEAN_NONE))
    out.update(public_lean(responses, key="official_lean", none_label=LEAN_NONE))
    out.update(public_lean(responses, key="outcome", none_label=outcome_none))
    return out


def screen_topic_transcript(
    client: JevClient,
    video_id: str,
    segments: Sequence[str],
    topic: TopicDef,
    *,
    pattern: re.Pattern[str] | None,
    chunk_chars: int,
    max_chunks: int,
    neighbors: int = 0,
) -> TopicLeanResult | None:
    """Ask Jev the topic's questions about one transcript. ``None`` if it has no text."""
    chunks = chunk_segments(segments, chunk_chars)
    if not chunks:
        return None
    picked, keyword_chunks = pick_keyword_chunks(chunks, pattern, max_chunks, neighbors=neighbors)
    selection, covered = chunk_coverage(chunks, picked, pattern, keyword_chunks)
    if selection == "keyword_passages" and neighbors:
        selection = f"keyword_passages+{neighbors}"
    questions = topic_questions(topic)
    responses: list[JevResponse] = []
    with llm_call_context(stage=f"jev_topic_lean:{topic.slug}", video_id=video_id):
        for index in picked:
            responses.append(client.system_one(state=chunks[index], questions=questions))
    tokens = [r.input_tokens for r in responses]
    return TopicLeanResult(
        video_id=video_id,
        topic=topic,
        model=responses[-1].model or client.model,
        chunk_count=len(chunks),
        chunks_screened=len(picked),
        keyword_chunks=keyword_chunks,
        chunk_selection=selection,
        passages_covered=covered,
        transcript_chars=sum(len(c) for c in chunks),
        input_tokens=sum(tokens) if all(t is not None for t in tokens) else None,
        answers=[{"chunk": i, "answers": r.raw.get("answers", {})} for i, r in zip(picked, responses)],
        **aggregate_topic(responses, outcome_none=topic.outcome_none),
    )


def select_sql(topic: TopicDef, *, rescreen: bool, states: Sequence[str] = ()) -> tuple[str, list[Any]]:
    """The topic's linked, captioned meetings, newest first. Those already screened at the topic's current question
    version are left out unless ``rescreen``. The caller appends the LIMIT parameter."""
    where = [
        "t.has_transcript IS TRUE",
        "t.video_id IN (SELECT video_id FROM public.topic_transcript_link WHERE topic_id = %s)",
    ]
    params: list[Any] = [topic.topic_id]
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    if state_list:
        where.append("e.state_code = ANY(%s)")
        params.append(state_list)
    if not rescreen:
        where.append(
            f"NOT EXISTS (SELECT 1 FROM {TABLE} s WHERE s.video_id = t.video_id "
            "AND s.topic_id = %s AND s.question_version = %s)"
        )
        params.extend([topic.topic_id, question_version(topic)])
    # Ids only: a full topic's transcripts are gigabytes, so each one is loaded when it is screened (TRANSCRIPT_SQL).
    sql = f"""
        SELECT DISTINCT ON (t.video_id) t.video_id, e.published_at
        FROM bronze.bronze_event_youtube_transcript t
        JOIN bronze.bronze_event_youtube e ON e.video_id = t.video_id
        WHERE {" AND ".join(where)}
        ORDER BY t.video_id, e.published_at DESC NULLS LAST
    """
    return f"SELECT video_id FROM ({sql}) v ORDER BY published_at DESC NULLS LAST, video_id LIMIT %s", params


TRANSCRIPT_SQL = """
    SELECT t.video_id, t.language, t.is_auto_generated, t.segments, t.caption_text_timed, t.raw_text
    FROM bronze.bronze_event_youtube_transcript t
    WHERE t.video_id = %s AND t.has_transcript IS TRUE
    LIMIT 1
"""


def _load_transcript(conn: Any, video_id: str) -> dict[str, Any] | None:
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(TRANSCRIPT_SQL, [video_id])
        row = cur.fetchone()
    return dict(row) if row else None


def topic_keywords(conn: Any, topic: TopicDef, *, wait_seconds: int = 1800, poll_seconds: int = 30) -> list[str]:
    """The topic's keyword phrases, as civicsearch_topic stores them (the ones the topic links matched).

    A dbt rebuild drops and re-creates the public views, so while public.civicsearch_topic or
    public.topic_transcript_link is missing this waits (up to ``wait_seconds``) instead of failing the run."""
    import time

    deadline = time.monotonic() + wait_seconds
    while True:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.civicsearch_topic') IS NOT NULL "
                "AND to_regclass('public.topic_transcript_link') IS NOT NULL"
            )
            ready = cur.fetchone()[0]
        conn.commit()
        if ready or time.monotonic() >= deadline:
            break
        logger.warning("public.civicsearch_topic / topic_transcript_link missing (a dbt rebuild?); waiting")
        time.sleep(poll_seconds)
    with conn.cursor() as cur:
        cur.execute("SELECT keyword_stats FROM public.civicsearch_topic WHERE topic_id = %s", [topic.topic_id])
        row = cur.fetchone()
    stats = row[0] if row else None
    if isinstance(stats, str):
        stats = json.loads(stats)
    if isinstance(stats, dict):
        return [str(k) for k in stats]
    return [str(k) for k in (stats or [])]


def resolve_topics(arg: str) -> list[TopicDef]:
    """``all``, one slug, or a comma-separated list of slugs."""
    slugs = list(TOPICS) if arg.strip() == "all" else [s.strip() for s in arg.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in TOPICS]
    if unknown or not slugs:
        raise SystemExit(f"Unknown topic(s): {', '.join(unknown) or arg!r}. Choose from: {', '.join(TOPICS)}, or all")
    return [TOPICS[s] for s in slugs]


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Screen each topic ``--topic`` names (``all``, a slug, or slugs separated by commas), one after another.
    ``--limit`` and ``--max-input-tokens`` apply per topic. Returns ``{"topics": {slug: summary}}``."""
    return {"topics": {t.slug: run_topic(args, topic=t) for t in resolve_topics(args.topic)}}


def run_topic(args: argparse.Namespace, *, topic: TopicDef | None = None) -> dict[str, Any]:
    """Screen one topic's meetings (``topic``, or the single slug in ``--topic``)."""
    import psycopg2

    from llm.typesafe.screen_transcripts import _database_url, _segment_texts
    from llm.usage.prices import load_prices, model_price

    topic = topic or TOPICS[args.topic]
    version = question_version(topic)
    neighbors = int(getattr(args, "neighbor_chunks", 0) or 0)
    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    conn = psycopg2.connect(database_url)
    try:
        if args.dry_run:
            # A dry run never writes (#1201): no DDL on the live table; with no table yet, nothing has been read.
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass(%s) IS NOT NULL", [TABLE])
                table_exists = cur.fetchone()[0]
            conn.rollback()
            sql, params = select_sql(topic, rescreen=args.rescreen or not table_exists, states=states)
        else:
            with conn.cursor() as cur:
                cur.execute(CREATE_SQL)
                cur.execute(ALTER_SQL)
            conn.commit()
            sql, params = select_sql(topic, rescreen=args.rescreen, states=states)
        keywords = topic_keywords(conn, topic)
        with conn.cursor() as cur:
            cur.execute(sql, [*params, args.limit])
            video_ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    pattern = keyword_pattern(keywords)
    logger.info(
        "{}: {:,} transcript(s) to screen (topic {}, questions {}, {} keywords)",
        topic.slug, len(video_ids), topic.topic_id, version, len(keywords),
    )
    summary: dict[str, Any] = {
        "topic": topic.slug, "selected": len(video_ids), "screened": 0, "empty": 0, "failed": 0, "input_tokens": 0,
    }
    if args.dry_run:
        est = 0
        conn = psycopg2.connect(database_url)
        try:
            for vid in video_ids:
                row = _load_transcript(conn, vid)
                chunks = chunk_segments(_segment_texts(row), args.chunk_chars) if row else []
                picked, _ = pick_keyword_chunks(chunks, pattern, args.max_chunks, neighbors=neighbors)
                est += sum(len(chunks[i]) for i in picked) // CHARS_PER_TOKEN
        finally:
            conn.close()
        rate = model_price("jev-", "interactive", load_prices())
        cost = f"${est * rate['input_usd_per_1m'] / 1_000_000:,.4f}" if rate else "no price on file"
        logger.success(
            "{} dry run: {:,} meeting(s) to read, ~{:,} input tokens, about {} at Jev's listed price. Nothing sent.",
            topic.slug, len(video_ids), est, cost,
        )
        summary["estimated_input_tokens"] = est
        return summary

    budget = int(getattr(args, "max_input_tokens", 0) or 0)
    n = len(video_ids)
    with JevClient(model=args.model or None) as client:
        conn = psycopg2.connect(database_url)
        try:
            for i, vid in enumerate(video_ids, 1):
                if budget and summary["input_tokens"] >= budget:
                    summary["stopped_at_budget"] = True
                    logger.warning("Stopping: {:,} input tokens reached the --max-input-tokens budget", budget)
                    break
                row = _load_transcript(conn, vid)
                conn.commit()
                if row is None:
                    summary["empty"] += 1
                    continue
                segments = _segment_texts(row)
                try:
                    try:
                        result = screen_topic_transcript(
                            client, vid, segments, topic,
                            pattern=pattern, chunk_chars=args.chunk_chars, max_chunks=args.max_chunks, neighbors=neighbors,
                        )
                    except JevError as exc:
                        # A chunk can tokenize past Jev's 32k limit (dense numbers, odd captions): retry at half size.
                        if "max_tokens_exceeded" not in str(exc):
                            raise
                        logger.info("[{}/{}] {}: a chunk is too long for Jev, retrying at half size", i, n, vid)
                        result = screen_topic_transcript(
                            client, vid, segments, topic,
                            pattern=pattern, chunk_chars=args.chunk_chars // 2, max_chunks=args.max_chunks, neighbors=neighbors,
                        )
                except JevError as exc:
                    summary["failed"] += 1
                    logger.warning("[{}/{}] {}: {}", i, n, vid, exc)
                    if exc.status_code in (401, 402, 403):
                        raise
                    continue
                if result is None:
                    summary["empty"] += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(UPSERT_SQL, result.row())
                conn.commit()
                summary["screened"] += 1
                summary["input_tokens"] += result.input_tokens or 0
                logger.info(
                    "[{}/{}] {} public={} official={} outcome={} ({} of {} chunks, {} with keywords; {:,} tokens so far)",
                    i, n, vid, result.public_lean, result.official_lean, result.outcome,
                    result.chunks_screened, result.chunk_count, result.keyword_chunks, summary["input_tokens"],
                )
        finally:
            conn.close()
    logger.success(
        "{topic}: screened {screened:,}, empty {empty:,}, failed {failed:,}; {input_tokens:,} input tokens".format(
            **summary
        )
    )
    return summary
