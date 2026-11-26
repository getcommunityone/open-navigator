"""Jev's reading of how the public and officials leaned on one topic, per meeting (#1126).

The data-center screen (``screen_transcripts``) asks data-center questions of every transcript. This asks the same
three questions for any curated topic, only of the meetings already linked to it (``public.topic_transcript_link``):

- ``public_lean`` (Choice): how the members of the public who spoke leaned on the topic: mostly_opposed,
  mostly_supportive, mixed, did_not_speak.
- ``official_lean`` (Choice): the same for the elected officials.
- ``outcome`` (Choice): what happened to an item on the topic (approved, denied, tabled, moratorium, discussed, none).

What "for" and "against" mean is fixed per topic in ``TOPICS`` (for pickleball, the courts or facility; for water
fluoridation, fluoride in the water), so the colours on a topic's map always point the same way.

Only the passages that name the topic are read (#1145): the transcript is cut into chunks at segment boundaries and up
to ``--max-chunks`` chunks that contain one of the topic's keywords (``curated_topics.keywords``) are sent. A long
meeting's public comment near the end is read; an unrelated first hour is not paid for. With no keyword hit (the link
came from elsewhere) the first chunk is read.

Answers land in ``bronze.bronze_transcript_topic_lean_jev``, one row per (video, topic, question version). Jev is a
classifier: probabilities only, no text, and every lean is a reading of the transcript, never a count of speakers.
Nothing is tied to a person.

Usage (paid: run only on the owner's go-ahead; read usage before and after, AGENTS.md)::

    python -m llm.typesafe.screen_transcripts --topic pickleball --limit 20 --dry-run
    python -m llm.typesafe.screen_transcripts --topic pickleball --limit 20
    python -m llm.typesafe.screen_transcripts --topic all
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from loguru import logger

from llm.typesafe.client import JevClient, JevError, JevResponse, choice

TABLE = "bronze.bronze_transcript_topic_lean_jev"

CHARS_PER_TOKEN = 4
# Smaller than the full screen's chunks: only the topic's passages are read, so a chunk is about 10k tokens.
DEFAULT_CHUNK_CHARS = 40_000
DEFAULT_MAX_CHUNKS = 3

# The repository's curated topics seed: the topic ids and the keywords that find the topic's passages.
SEED_PATH = Path(__file__).resolve().parents[5] / "dbt_project" / "seeds" / "curated_topics.csv"


@dataclass(frozen=True)
class TopicDef:
    """One topic's wording. ``thing`` is what is being discussed; ``stance`` is what "for" and "against" are about."""

    slug: str
    topic_id: int
    thing: str
    stance: str
    item: str


# Data centers keep their own screen and columns (screen_transcripts, data_center_meeting_lean).
TOPICS: dict[str, TopicDef] = {
    "short-term-rentals": TopicDef(
        slug="short-term-rentals",
        topic_id=100003,
        thing="short-term rentals of homes (Airbnb, VRBO and other vacation rentals)",
        stance="allowing short-term rentals (permits, fewer limits); against means banning or restricting them",
        item="short-term rental",
    ),
    "license-plate-readers": TopicDef(
        slug="license-plate-readers",
        topic_id=100004,
        thing="automated license plate reader cameras (Flock Safety and similar)",
        stance="buying, keeping or expanding license plate reader cameras; against means rejecting or removing them",
        item="license plate reader",
    ),
    "guns": TopicDef(
        slug="guns",
        topic_id=100005,
        thing="firearms: gun rules, gun shows, shooting ranges, gun stores and gunshot detection (ShotSpotter)",
        stance=(
            "the firearm-related proposal before the body (a range, show, store, rule or detection contract); "
            "against means opposing that proposal"
        ),
        item="firearm-related",
    ),
    "pickleball": TopicDef(
        slug="pickleball",
        topic_id=100006,
        thing="pickleball: public courts, private pickleball venues, and their noise, lights and parking",
        stance="building, keeping or expanding the pickleball courts or venue; against means opposing them",
        item="pickleball",
    ),
    "water-fluoridation": TopicDef(
        slug="water-fluoridation",
        topic_id=100002,
        thing="adding fluoride to the public drinking water",
        stance="keeping or adding fluoride in the water; against means ending or opposing fluoridation",
        item="water fluoridation",
    ),
    "bike-lanes": TopicDef(
        slug="bike-lanes",
        topic_id=100007,
        thing="bike lanes, bike paths and other bicycle infrastructure",
        stance="building or keeping the bike lanes or paths; against means opposing or removing them",
        item="bike lane",
    ),
}

LEAN_NONE = "did_not_speak"


def _public(t: TopicDef) -> str:
    return (
        "members of the public who spoke (residents, local business owners, advocacy groups), not elected "
        f"officials, government staff, consultants, or an applicant or their representatives, about {t.thing}"
    )


def _officials(t: TopicDef) -> str:
    return f"the elected officials (council, commission or board members), not staff and not the public, on {t.thing}"


def questions_for(t: TopicDef) -> dict[str, dict[str, Any]]:
    """The three Jev questions for one topic. Their wording is hashed into the question version."""
    pub, off = _public(t), _officials(t)
    lean = {
        "mostly_opposed": "Most of them who spoke were against {s}",
        "mostly_supportive": "Most of them who spoke were in favor of {s}",
        "mixed": "Some of them spoke in favor of and others against {s}",
    }
    return {
        "public_lean": choice(
            f"How {pub} leaned. 'In favor' means in favor of {t.stance}.",
            {**{k: v.format(s=t.stance) for k, v in lean.items()},
             LEAN_NONE: f"None of the members of the public spoke for or against {t.thing}"},
        ),
        "official_lean": choice(
            f"How {off} leaned. 'In favor' means in favor of {t.stance}.",
            {**{k: v.format(s=t.stance) for k, v in lean.items()},
             LEAN_NONE: f"None of the elected officials took a position on {t.thing}"},
        ),
        "outcome": choice(
            f"What happened to a {t.item} item in this meeting",
            {
                "approved": f"A {t.item} item was approved, adopted, granted or funded",
                "denied": f"A {t.item} item was denied, rejected or voted down",
                "tabled_or_deferred": f"A {t.item} item was tabled, deferred, continued or postponed",
                "moratorium": f"A pause or moratorium on {t.item} items was adopted or extended",
                "discussed_no_action": f"A {t.item} matter was discussed, but no vote or action on it was taken",
                "no_item": f"No {t.item} item or matter was discussed",
            },
        ),
    }


def question_version(t: TopicDef) -> str:
    """Changes whenever the topic's wording changes, so a rewording is screened again."""
    return hashlib.sha256(json.dumps(questions_for(t), sort_keys=True).encode()).hexdigest()[:12]


def load_keywords(path: Path = SEED_PATH) -> dict[int, list[str]]:
    """Each curated topic's keywords, by topic id, from the seed (the same phrases that link meetings to it)."""
    out: dict[int, list[str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kws = [k.strip().lower() for k in (row.get("keywords") or "").split("|") if k.strip()]
            out[int(row["topic_id"])] = kws
    return out


def keyword_regex(keywords: Iterable[str]) -> re.Pattern[str] | None:
    """Whole-word, case-insensitive alternation of the keywords; None with none."""
    kws = sorted({k for k in keywords if k}, key=len, reverse=True)
    if not kws:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")\b", re.IGNORECASE)


def topic_chunks(chunks: Sequence[str], pattern: re.Pattern[str] | None, max_chunks: int) -> list[int]:
    """The chunks to read: those naming the topic, most keyword hits first, at most ``max_chunks``, in transcript
    order. With no hit, the first chunk."""
    if not chunks:
        return []
    if max_chunks <= 0:
        raise ValueError("max_chunks must be positive")
    hits = [(len(pattern.findall(c)) if pattern else 0, i) for i, c in enumerate(chunks)]
    named = [(n, i) for n, i in hits if n > 0]
    if not named:
        return [0]
    best = sorted(named, key=lambda x: (-x[0], x[1]))[:max_chunks]
    return sorted(i for _, i in best)


def lean_from(responses: Sequence[Any], key: str, *, min_spoke_p: float = 0.5) -> dict[str, Any]:
    """A lean over the chunks read: averaged only over chunks where it is likely someone spoke on the topic
    (P(did_not_speak) < 1 - ``min_spoke_p``), as the data-center reading does (#1113). None of them: did_not_speak."""
    dists = [r.answers[key].probabilities for r in responses if key in r.answers and r.answers[key].probabilities]
    if not dists:
        return {key: None, f"{key}_probabilities": None}
    spoke = [d for d in dists if d.get(LEAN_NONE, 0.0) < 1.0 - min_spoke_p]
    if not spoke:
        return {key: LEAN_NONE, f"{key}_probabilities": {LEAN_NONE: round(min(d.get(LEAN_NONE, 0.0) for d in dists), 4)}}
    sums: dict[str, float] = {}
    for d in spoke:
        for label, p in d.items():
            if label != LEAN_NONE:
                sums[label] = sums.get(label, 0.0) + p
    total = sum(sums.values()) or 1.0
    dist = {k: round(v / total, 4) for k, v in sums.items()}
    return {key: max(dist, key=dist.get), f"{key}_probabilities": dist}


def outcome_from(responses: Sequence[Any]) -> dict[str, Any]:
    """The outcome averaged over the chunks read."""
    sums: dict[str, float] = {}
    n = 0
    for r in responses:
        a = r.answers.get("outcome")
        if a and a.probabilities:
            n += 1
            for label, p in a.probabilities.items():
                sums[label] = sums.get(label, 0.0) + p
    dist = {k: round(v / n, 4) for k, v in sums.items()} if n else {}
    return {"outcome": max(dist, key=dist.get) if dist else None, "outcome_probabilities": dist or None}


@dataclass
class TopicLeanResult:
    video_id: str
    topic_id: int
    question_version: str
    model: str
    chunk_count: int
    chunks_screened: int
    input_tokens: int | None
    public_lean: str | None
    public_lean_probabilities: dict[str, float] | None
    official_lean: str | None
    official_lean_probabilities: dict[str, float] | None
    outcome: str | None
    outcome_probabilities: dict[str, float] | None
    answers: list[dict[str, Any]]

    def row(self) -> dict[str, Any]:
        j = lambda v: json.dumps(v) if v is not None else None  # noqa: E731
        return {
            "video_id": self.video_id,
            "topic_id": self.topic_id,
            "question_version": self.question_version,
            "model": self.model,
            "chunk_count": self.chunk_count,
            "chunks_screened": self.chunks_screened,
            "input_tokens": self.input_tokens,
            "public_lean": self.public_lean,
            "public_lean_probabilities": j(self.public_lean_probabilities),
            "official_lean": self.official_lean,
            "official_lean_probabilities": j(self.official_lean_probabilities),
            "outcome": self.outcome,
            "outcome_probabilities": j(self.outcome_probabilities),
            "answers": json.dumps(self.answers),
            "screened_at": datetime.now(UTC),
        }


CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    video_id                     text        NOT NULL,
    topic_id                     integer     NOT NULL,
    question_version             text        NOT NULL,
    model                        text,
    chunk_count                  integer,
    chunks_screened              integer,
    input_tokens                 integer,
    public_lean                  text,
    public_lean_probabilities    jsonb,
    official_lean                text,
    official_lean_probabilities  jsonb,
    outcome                      text,
    outcome_probabilities        jsonb,
    answers                      jsonb,
    screened_at                  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, topic_id, question_version)
)
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE} (
    video_id, topic_id, question_version, model, chunk_count, chunks_screened, input_tokens,
    public_lean, public_lean_probabilities, official_lean, official_lean_probabilities,
    outcome, outcome_probabilities, answers, screened_at
) VALUES (
    %(video_id)s, %(topic_id)s, %(question_version)s, %(model)s, %(chunk_count)s, %(chunks_screened)s,
    %(input_tokens)s, %(public_lean)s, %(public_lean_probabilities)s, %(official_lean)s,
    %(official_lean_probabilities)s, %(outcome)s, %(outcome_probabilities)s, %(answers)s, %(screened_at)s
)
ON CONFLICT (video_id, topic_id, question_version) DO UPDATE SET
    model = EXCLUDED.model,
    chunk_count = EXCLUDED.chunk_count,
    chunks_screened = EXCLUDED.chunks_screened,
    input_tokens = EXCLUDED.input_tokens,
    public_lean = EXCLUDED.public_lean,
    public_lean_probabilities = EXCLUDED.public_lean_probabilities,
    official_lean = EXCLUDED.official_lean,
    official_lean_probabilities = EXCLUDED.official_lean_probabilities,
    outcome = EXCLUDED.outcome,
    outcome_probabilities = EXCLUDED.outcome_probabilities,
    answers = EXCLUDED.answers,
    screened_at = EXCLUDED.screened_at
"""


def select_sql(t: TopicDef, *, states: Iterable[str], rescreen: bool) -> tuple[str, list[Any]]:
    """The topic's linked meetings with a transcript, newest first; those already read with the current wording are
    left out unless ``rescreen``. The caller appends the LIMIT parameter."""
    where = ["t.has_transcript IS TRUE", "l.topic_id = %s"]
    params: list[Any] = [t.topic_id]
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    if state_list:
        where.append("l.state_code = ANY(%s)")
        params.append(state_list)
    if not rescreen:
        where.append(
            f"NOT EXISTS (SELECT 1 FROM {TABLE} s WHERE s.video_id = t.video_id "
            "AND s.topic_id = %s AND s.question_version = %s)"
        )
        params.extend([t.topic_id, question_version(t)])
    sql = f"""
        SELECT DISTINCT ON (t.video_id)
               t.video_id, t.segments, t.caption_text_timed, t.raw_text, l.event_date
        FROM public.topic_transcript_link l
        JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = l.video_id
        WHERE {" AND ".join(where)}
        ORDER BY t.video_id, l.event_date DESC NULLS LAST
    """
    return f"SELECT * FROM ({sql}) v ORDER BY event_date DESC NULLS LAST LIMIT %s", params


def screen_one(
    client: JevClient,
    t: TopicDef,
    video_id: str,
    segments: Sequence[str],
    pattern: re.Pattern[str] | None,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> TopicLeanResult | None:
    """Ask the topic's questions of the passages that name it. None when the transcript has no text."""
    from llm.typesafe.screen_transcripts import chunk_segments
    from llm.usage.calls import llm_call_context

    chunks = chunk_segments(segments, chunk_chars)
    if not chunks:
        return None
    picked = topic_chunks(chunks, pattern, max_chunks)
    qs = questions_for(t)
    responses: list[JevResponse] = []
    with llm_call_context(stage=f"jev_topic_lean:{t.slug}", video_id=video_id):
        for i in picked:
            responses.append(client.system_one(state=chunks[i], questions=qs))
    tokens = [r.input_tokens for r in responses]
    return TopicLeanResult(
        video_id=video_id,
        topic_id=t.topic_id,
        question_version=question_version(t),
        model=responses[-1].model or client.model,
        chunk_count=len(chunks),
        chunks_screened=len(picked),
        input_tokens=sum(tokens) if all(x is not None for x in tokens) else None,
        answers=[{"chunk": i, "answers": r.raw.get("answers", {})} for i, r in zip(picked, responses)],
        **lean_from(responses, "public_lean"),
        **lean_from(responses, "official_lean"),
        **outcome_from(responses),
    )


def estimate_tokens(segments: Sequence[str], pattern: re.Pattern[str] | None, *, chunk_chars: int, max_chunks: int) -> int:
    from llm.typesafe.screen_transcripts import chunk_segments

    chunks = chunk_segments(segments, chunk_chars)
    return sum(len(chunks[i]) for i in topic_chunks(chunks, pattern, max_chunks)) // CHARS_PER_TOKEN


def resolve_topics(arg: str) -> list[TopicDef]:
    """``all`` or a comma-separated list of slugs."""
    slugs = list(TOPICS) if arg.strip() == "all" else [s.strip() for s in arg.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in TOPICS]
    if unknown:
        raise SystemExit(f"Unknown topic(s): {', '.join(unknown)}. Choose from: {', '.join(TOPICS)}, or all")
    return [TOPICS[s] for s in slugs]


def run(args: Any) -> dict[str, Any]:
    """Screen each asked topic's meetings. ``--dry-run`` estimates tokens and cost and sends nothing."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    from llm.typesafe.screen_transcripts import _database_url, _segment_texts
    from llm.usage.prices import load_prices, model_price

    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    keywords = load_keywords()
    chunk_chars = args.topic_chunk_chars or DEFAULT_CHUNK_CHARS
    max_chunks = args.topic_max_chunks or DEFAULT_MAX_CHUNKS
    summary: dict[str, Any] = {"topics": {}}

    for t in resolve_topics(args.topic):
        pattern = keyword_regex(keywords.get(t.topic_id, []))
        sql, params = select_sql(t, states=states, rescreen=args.rescreen)
        conn = psycopg2.connect(database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(CREATE_SQL)
            conn.commit()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, [*params, args.limit])
                rows = cur.fetchall()
        finally:
            conn.close()
        s = {"selected": len(rows), "screened": 0, "empty": 0, "failed": 0, "input_tokens": 0}
        summary["topics"][t.slug] = s
        logger.info("{}: {:,} meeting(s) to read (questions {})", t.slug, len(rows), question_version(t))

        if args.dry_run:
            est = sum(estimate_tokens(_segment_texts(r), pattern, chunk_chars=chunk_chars, max_chunks=max_chunks) for r in rows)
            rate = model_price("jev-", "interactive", load_prices())
            cost = f"${est * rate['input_usd_per_1m'] / 1_000_000:,.4f}" if rate else "no price on file"
            logger.success("{} dry run: ~{:,} input tokens, about {}. Nothing sent.", t.slug, est, cost)
            s["estimated_input_tokens"] = est
            continue

        with JevClient(model=args.model or None) as client:
            conn = psycopg2.connect(database_url)
            try:
                for i, row in enumerate(rows, 1):
                    vid = row["video_id"]
                    try:
                        result = screen_one(
                            client, t, vid, _segment_texts(row), pattern, chunk_chars=chunk_chars, max_chunks=max_chunks
                        )
                    except JevError as exc:
                        s["failed"] += 1
                        logger.warning("[{} {}/{}] {}: {}", t.slug, i, len(rows), vid, exc)
                        if exc.status_code in (401, 403):
                            raise
                        continue
                    if result is None:
                        s["empty"] += 1
                        continue
                    with conn.cursor() as cur:
                        cur.execute(UPSERT_SQL, result.row())
                    conn.commit()
                    s["screened"] += 1
                    s["input_tokens"] += result.input_tokens or 0
                    logger.info(
                        "[{} {}/{}] {} public={} officials={} outcome={} ({} of {} chunks)",
                        t.slug, i, len(rows), vid, result.public_lean, result.official_lean, result.outcome,
                        result.chunks_screened, result.chunk_count,
                    )
            finally:
                conn.close()
        logger.success(
            "{}: read {screened:,}, empty {empty:,}, failed {failed:,}; {input_tokens:,} input tokens".format(t.slug, **s)
        )
    return summary
