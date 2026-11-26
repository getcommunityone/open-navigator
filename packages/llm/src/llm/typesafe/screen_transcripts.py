"""Screen meeting transcripts with Jev before the paid Gemini analysis.

For each captioned video not yet screened, Jev answers meeting-kind / decision /
data-center questions plus light topic Noul flags (same request — #702 / #703):

- ``meeting_kind`` (Choice): governing-body meeting, town hall, other government
  video (press conference, ceremony, training), or not government at all.
- ``has_decisions`` (Noul): the body votes on or approves something.
- ``mentions_data_center`` (Noul): a data center is discussed.
- ``mentions_zoning``, ``mentions_budget``, ``mentions_housing``,
  ``mentions_environment`` (Noul): light topic flags for browse without Gemini.

The answers land in ``bronze.bronze_transcript_screen_jev``, one row per video.
``llm.gemini.batch_backlog submit --skip-jev-below P`` then leaves out videos whose
``has_decisions_p`` is below ``P``. Nothing is skipped until someone passes that
flag, and the screen never changes or deletes a transcript.

Long transcripts: Jev reads at most 32k tokens per question
(https://docs.typesafe.ai/models.md), so a transcript is cut into chunks at segment
boundaries. Up to ``--max-chunks`` evenly spaced chunks are screened (always the
first and the last). ``meeting_kind`` averages the chunks' probabilities; each Noul
takes the highest chunk, so a vote anywhere in the meeting counts and a video is
only skippable when no screened chunk shows one.

Usage::

    python -m llm.typesafe.screen_transcripts --state AL --limit 50 --dry-run
    python -m llm.typesafe.screen_transcripts --state AL --limit 50
    python -m llm.typesafe.screen_transcripts --jurisdiction-id tuscaloosa_0177256
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Sequence

from loguru import logger

from llm.typesafe.client import JevClient, JevError, JevResponse, choice, noul
from llm.usage.calls import llm_call_context

TABLE = "bronze.bronze_transcript_screen_jev"

# Rough English average; used only to size chunks and estimate cost before a run.
CHARS_PER_TOKEN = 4
# 32k tokens per question, minus room for the question text.
DEFAULT_CHUNK_CHARS = 100_000
DEFAULT_MAX_CHUNKS = 4

MEETING_KINDS = {
    "government_meeting": (
        "An official public meeting of a governing body: a city or town council, county "
        "commission, school board, planning or zoning board, authority, or a public hearing"
    ),
    "town_hall": (
        "A government town hall or community listening session: elected officials or staff "
        "taking public comment or Q&A with residents, without (or aside from) a formal vote "
        "of a governing body"
    ),
    "government_other": (
        "A government video that isn't a governing-body meeting or town hall: a press "
        "conference, ceremony, proclamation event, training, or public service announcement"
    ),
    "not_government": (
        "Not a government video: entertainment, sports, worship service, news commentary, "
        "a business or a private event"
    ),
}

# Probabilities summed for ``--skip-jev-meeting-below`` (meetings + town halls stay in).
MEETING_KEEP_KIND_KEYS: tuple[str, ...] = ("government_meeting", "town_hall")

# Light topic flags (#703) — same Jev request as the screen; nearly free once state is paid.
TOPIC_NOUL_KEYS: tuple[str, ...] = (
    "mentions_zoning",
    "mentions_budget",
    "mentions_housing",
    "mentions_environment",
    "mentions_short_term_rentals",
)

# Featured policy questions (public.policy_question, is_featured), #1029. The slug is ours; dbt maps it to the
# registry's question_id by canonical_text. Asked in the same request: Jev prices the transcript, not the questions.
POLICY_QUESTIONS: dict[str, dict[str, str]] = {
    "allow_data_centers": {
        "canonical_text": "Should we allow new data centers?",
        "noul": "The meeting debates whether to allow, approve, rezone for, restrict or pause a data center",
    },
    "allow_short_term_rentals": {
        "canonical_text": "Should we allow short-term rentals?",
        "noul": "The meeting debates whether to allow, permit, regulate or restrict short-term rentals "
        "(Airbnb, VRBO, vacation rentals)",
    },
    "build_bike_lanes": {
        "canonical_text": "Should we build bike lanes and paths?",
        "noul": "The meeting debates whether to build, fund or remove bike lanes, bike paths or greenway trails",
    },
    "license_plate_readers": {
        "canonical_text": "Should police use automated license plate readers?",
        "noul": "The meeting debates whether police should use automated license plate readers or Flock cameras",
    },
    "no_bid_contracts": {
        "canonical_text": "Should the jurisdiction award no-bid contracts?",
        "noul": "The meeting debates awarding a contract without competitive bidding (a no-bid or sole-source contract)",
    },
}


def _outcomes(thing: str, none_key: str) -> dict[str, str]:
    """The outcome choices for one kind of item (#1029)."""
    return {
        "approved": f"A {thing} item was approved, adopted or granted (permit, rezoning, ordinance, agreement)",
        "denied": f"A {thing} item was denied, rejected or voted down",
        "tabled_or_deferred": f"A {thing} item was tabled, deferred, continued or postponed to a later meeting",
        "moratorium": f"A pause or moratorium on {thing}s was adopted or extended",
        "discussed_no_action": f"A {thing} was discussed, but no vote or action on it was taken",
        none_key: f"No {thing} was discussed",
    }


DC_OUTCOMES = _outcomes("data center", "no_data_center_item")
STR_OUTCOMES = _outcomes("short-term rental", "no_short_term_rental_item")
# How the public leaned on a data center (#1113): members of the public, not officials or staff.
DC_PUBLIC_LEAN = {
    "mostly_opposed": "Most members of the public who spoke about a data center opposed it",
    "mostly_supported": "Most members of the public who spoke about a data center supported it",
    "mixed": "Members of the public who spoke about a data center were split between support and opposition",
    "no_public_comment_on_data_center": "No member of the public spoke about a data center",
}
DC_LEAN_NONE = "no_public_comment_on_data_center"
# Choice answers averaged across chunks and stored as <key> + <key>_probabilities (#1029).
OUTCOME_KEYS: tuple[str, ...] = ("dc_outcome", "str_outcome")

QUESTIONS: dict[str, dict[str, Any]] = {
    "meeting_kind": choice(
        "What kind of video this transcript comes from", MEETING_KINDS
    ),
    "has_decisions": noul(
        "The transcript records the body voting on, approving, adopting, denying or tabling "
        "a motion, ordinance, resolution, contract, budget item, rezoning or appointment"
    ),
    "mentions_data_center": noul(
        "The transcript discusses a data center: a proposed, approved or operating facility, "
        "its zoning, tax deal, power or water use, or residents' views on one"
    ),
    "mentions_zoning": noul(
        "The transcript discusses zoning, land use, site plans, special exceptions, "
        "variances, annexation, or a planning/zoning board decision"
    ),
    "mentions_budget": noul(
        "The transcript discusses a budget, tax or millage rate, bond issue, appropriation, "
        "or a material contract / spend approval"
    ),
    "mentions_housing": noul(
        "The transcript discusses housing, affordable housing, homelessness housing programs, "
        "or residential density / multifamily zoning"
    ),
    "mentions_environment": noul(
        "The transcript discusses water, sewer, stormwater, electric power or utilities capacity, "
        "or an environmental impact / pollution concern (including data-center utilities)"
    ),
    "mentions_short_term_rentals": noul(
        "The transcript discusses short-term rentals: Airbnb, VRBO, vacation rentals, their permits, "
        "registration, taxes, density limits or neighbors' complaints"
    ),
    "dc_outcome": choice("What happened to a data center item in this meeting", DC_OUTCOMES),
    "str_outcome": choice("What happened to a short-term rental item in this meeting", STR_OUTCOMES),
    "dc_public_lean": choice(
        "How the members of the public (not officials or staff) who spoke about a data center leaned",
        DC_PUBLIC_LEAN,
    ),
    **{f"q_{slug}": noul(spec["noul"]) for slug, spec in POLICY_QUESTIONS.items()},
}

# Changes whenever a question's wording changes, so a rewording can be rescreened.
QUESTION_VERSION = hashlib.sha256(
    json.dumps(QUESTIONS, sort_keys=True).encode()
).hexdigest()[:12]

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    video_id                    text PRIMARY KEY,
    question_version            text NOT NULL,
    model                       text NOT NULL,
    meeting_kind                text,
    meeting_kind_probabilities  jsonb,
    has_decisions_p             double precision,
    mentions_data_center_p      double precision,
    mentions_zoning_p           double precision,
    mentions_budget_p           double precision,
    mentions_housing_p          double precision,
    mentions_environment_p      double precision,
    mentions_short_term_rentals_p double precision,
    dc_outcome                  text,
    dc_outcome_probabilities    jsonb,
    str_outcome                 text,
    str_outcome_probabilities   jsonb,
    dc_public_lean              text,
    dc_public_lean_probabilities jsonb,
    question_probabilities      jsonb,
    chunk_count                 integer NOT NULL,
    chunks_screened             integer NOT NULL,
    transcript_chars            integer NOT NULL,
    input_tokens                integer,
    answers                     jsonb NOT NULL,
    screened_at                 timestamptz NOT NULL DEFAULT now()
)
"""

# Additive columns for DBs created before #703 topic flags.
ALTER_TOPIC_COLUMNS_SQL = f"""
ALTER TABLE {TABLE}
    ADD COLUMN IF NOT EXISTS mentions_zoning_p double precision,
    ADD COLUMN IF NOT EXISTS mentions_budget_p double precision,
    ADD COLUMN IF NOT EXISTS mentions_housing_p double precision,
    ADD COLUMN IF NOT EXISTS mentions_environment_p double precision,
    ADD COLUMN IF NOT EXISTS mentions_short_term_rentals_p double precision,
    ADD COLUMN IF NOT EXISTS dc_outcome text,
    ADD COLUMN IF NOT EXISTS dc_outcome_probabilities jsonb,
    ADD COLUMN IF NOT EXISTS str_outcome text,
    ADD COLUMN IF NOT EXISTS str_outcome_probabilities jsonb,
    ADD COLUMN IF NOT EXISTS question_probabilities jsonb,
    ADD COLUMN IF NOT EXISTS dc_public_lean text,
    ADD COLUMN IF NOT EXISTS dc_public_lean_probabilities jsonb
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE} (
    video_id, question_version, model, meeting_kind, meeting_kind_probabilities,
    has_decisions_p, mentions_data_center_p,
    mentions_zoning_p, mentions_budget_p, mentions_housing_p, mentions_environment_p,
    mentions_short_term_rentals_p, dc_outcome, dc_outcome_probabilities, str_outcome, str_outcome_probabilities,
    question_probabilities, dc_public_lean, dc_public_lean_probabilities,
    chunk_count, chunks_screened,
    transcript_chars, input_tokens, answers, screened_at
) VALUES (
    %(video_id)s, %(question_version)s, %(model)s, %(meeting_kind)s,
    %(meeting_kind_probabilities)s, %(has_decisions_p)s, %(mentions_data_center_p)s,
    %(mentions_zoning_p)s, %(mentions_budget_p)s, %(mentions_housing_p)s,
    %(mentions_environment_p)s,
    %(mentions_short_term_rentals_p)s, %(dc_outcome)s, %(dc_outcome_probabilities)s, %(str_outcome)s,
    %(str_outcome_probabilities)s, %(question_probabilities)s, %(dc_public_lean)s,
    %(dc_public_lean_probabilities)s,
    %(chunk_count)s, %(chunks_screened)s, %(transcript_chars)s, %(input_tokens)s,
    %(answers)s, %(screened_at)s
)
ON CONFLICT (video_id) DO UPDATE SET
    question_version = EXCLUDED.question_version,
    model = EXCLUDED.model,
    meeting_kind = EXCLUDED.meeting_kind,
    meeting_kind_probabilities = EXCLUDED.meeting_kind_probabilities,
    has_decisions_p = EXCLUDED.has_decisions_p,
    mentions_data_center_p = EXCLUDED.mentions_data_center_p,
    mentions_zoning_p = EXCLUDED.mentions_zoning_p,
    mentions_budget_p = EXCLUDED.mentions_budget_p,
    mentions_housing_p = EXCLUDED.mentions_housing_p,
    mentions_environment_p = EXCLUDED.mentions_environment_p,
    mentions_short_term_rentals_p = EXCLUDED.mentions_short_term_rentals_p,
    dc_outcome = EXCLUDED.dc_outcome,
    dc_outcome_probabilities = EXCLUDED.dc_outcome_probabilities,
    str_outcome = EXCLUDED.str_outcome,
    str_outcome_probabilities = EXCLUDED.str_outcome_probabilities,
    question_probabilities = EXCLUDED.question_probabilities,
    dc_public_lean = EXCLUDED.dc_public_lean,
    dc_public_lean_probabilities = EXCLUDED.dc_public_lean_probabilities,
    chunk_count = EXCLUDED.chunk_count,
    chunks_screened = EXCLUDED.chunks_screened,
    transcript_chars = EXCLUDED.transcript_chars,
    input_tokens = EXCLUDED.input_tokens,
    answers = EXCLUDED.answers,
    screened_at = EXCLUDED.screened_at
"""


@dataclass(frozen=True)
class ScreenResult:
    """One video's screen, ready to write."""

    video_id: str
    model: str
    meeting_kind: str | None
    meeting_kind_probabilities: dict[str, float]
    has_decisions_p: float | None
    mentions_data_center_p: float | None
    mentions_zoning_p: float | None
    mentions_budget_p: float | None
    mentions_housing_p: float | None
    mentions_environment_p: float | None
    chunk_count: int
    chunks_screened: int
    transcript_chars: int
    input_tokens: int | None
    answers: list[dict[str, Any]]
    # #1029: short-term rental flag, the two outcome Choices and the policy-question Nouls.
    mentions_short_term_rentals_p: float | None = None
    dc_outcome: str | None = None
    dc_outcome_probabilities: dict[str, float] | None = None
    str_outcome: str | None = None
    str_outcome_probabilities: dict[str, float] | None = None
    question_probabilities: dict[str, float] | None = None
    # #1113: how the public leaned on a data center, over the chunks where the public spoke about one.
    dc_public_lean: str | None = None
    dc_public_lean_probabilities: dict[str, float] | None = None

    def row(self, *, screened_at: datetime | None = None) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "question_version": QUESTION_VERSION,
            "model": self.model,
            "meeting_kind": self.meeting_kind,
            "meeting_kind_probabilities": json.dumps(self.meeting_kind_probabilities),
            "has_decisions_p": self.has_decisions_p,
            "mentions_data_center_p": self.mentions_data_center_p,
            "mentions_zoning_p": self.mentions_zoning_p,
            "mentions_budget_p": self.mentions_budget_p,
            "mentions_housing_p": self.mentions_housing_p,
            "mentions_environment_p": self.mentions_environment_p,
            "mentions_short_term_rentals_p": self.mentions_short_term_rentals_p,
            "dc_outcome": self.dc_outcome,
            "dc_outcome_probabilities": json.dumps(self.dc_outcome_probabilities) if self.dc_outcome_probabilities is not None else None,
            "str_outcome": self.str_outcome,
            "str_outcome_probabilities": json.dumps(self.str_outcome_probabilities) if self.str_outcome_probabilities is not None else None,
            "question_probabilities": json.dumps(self.question_probabilities) if self.question_probabilities is not None else None,
            "dc_public_lean": self.dc_public_lean,
            "dc_public_lean_probabilities": json.dumps(self.dc_public_lean_probabilities) if self.dc_public_lean_probabilities is not None else None,
            "chunk_count": self.chunk_count,
            "chunks_screened": self.chunks_screened,
            "transcript_chars": self.transcript_chars,
            "input_tokens": self.input_tokens,
            "answers": json.dumps(self.answers),
            "screened_at": screened_at or datetime.now(UTC),
        }


def chunk_segments(
    segments: Sequence[str], max_chars: int = DEFAULT_CHUNK_CHARS
) -> list[str]:
    """Join segment texts into chunks of at most ``max_chars``, breaking between segments.

    A single segment longer than ``max_chars`` is split on its own."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for raw in segments:
        text = " ".join(str(raw).split())
        if not text:
            continue
        pieces = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
        for piece in pieces:
            extra = len(piece) + (1 if current else 0)
            if current and size + extra > max_chars:
                chunks.append(" ".join(current))
                current, size = [], 0
                extra = len(piece)
            current.append(piece)
            size += extra
    if current:
        chunks.append(" ".join(current))
    return chunks


def pick_chunks(
    chunks: Sequence[str], max_chunks: int = DEFAULT_MAX_CHUNKS
) -> list[int]:
    """Indexes of up to ``max_chunks`` evenly spaced chunks, always the first and last."""
    n = len(chunks)
    if n == 0:
        return []
    if max_chunks <= 0:
        raise ValueError("max_chunks must be positive")
    if n <= max_chunks:
        return list(range(n))
    if max_chunks == 1:
        return [0]
    step = (n - 1) / (max_chunks - 1)
    return sorted({round(i * step) for i in range(max_chunks)})


def aggregate(responses: Sequence[JevResponse]) -> dict[str, Any]:
    """Combine per-chunk answers: average the Choice probabilities, take each Noul's max."""
    kinds: dict[str, float] = {}
    counted = 0
    for resp in responses:
        answer = resp.answers.get("meeting_kind")
        if answer and answer.probabilities:
            counted += 1
            for label, p in answer.probabilities.items():
                kinds[label] = kinds.get(label, 0.0) + p
    probs = {k: round(v / counted, 4) for k, v in kinds.items()} if counted else {}
    meeting_kind = max(probs, key=probs.get) if probs else None

    def _max_noul(name: str) -> float | None:
        values = [
            r.answers[name].noul
            for r in responses
            if name in r.answers and r.answers[name].noul is not None
        ]
        return max(values) if values else None

    out: dict[str, Any] = {
        "meeting_kind": meeting_kind,
        "meeting_kind_probabilities": probs,
        "has_decisions_p": _max_noul("has_decisions"),
        "mentions_data_center_p": _max_noul("mentions_data_center"),
    }
    for key in TOPIC_NOUL_KEYS:
        out[f"{key}_p"] = _max_noul(key)
    # Outcome Choices (#1029): average each label across the chunks that answered.
    for key in OUTCOME_KEYS:
        sums: dict[str, float] = {}
        n = 0
        for resp in responses:
            a = resp.answers.get(key)
            if a and a.probabilities:
                n += 1
                for label, prob in a.probabilities.items():
                    sums[label] = sums.get(label, 0.0) + prob
        dist = {k: round(v / n, 4) for k, v in sums.items()} if n else {}
        out[key] = max(dist, key=dist.get) if dist else None
        out[f"{key}_probabilities"] = dist or None
    out.update(public_lean(responses))
    # Policy questions (#1029): debated anywhere in the meeting, so the max over chunks.
    questions = {slug: _max_noul(f"q_{slug}") for slug in POLICY_QUESTIONS}
    out["question_probabilities"] = {k: v for k, v in questions.items() if v is not None} or None
    return out


def public_lean(responses: Sequence[JevResponse], *, min_spoke_p: float = 0.5) -> dict[str, Any]:
    """How the public leaned on a data center (#1113). Averaged only over the chunks where Jev judges it likely the
    public spoke about one (P(no public comment) < 1 - ``min_spoke_p``), so the rest of a long meeting doesn't drown
    it out. No such chunk: ``no_public_comment_on_data_center``."""
    dists = []
    for resp in responses:
        a = resp.answers.get("dc_public_lean")
        if a and a.probabilities:
            dists.append(a.probabilities)
    if not dists:
        return {"dc_public_lean": None, "dc_public_lean_probabilities": None}
    spoke = [d for d in dists if d.get(DC_LEAN_NONE, 0.0) < 1.0 - min_spoke_p]
    if not spoke:
        return {
            "dc_public_lean": DC_LEAN_NONE,
            "dc_public_lean_probabilities": {DC_LEAN_NONE: round(min(d.get(DC_LEAN_NONE, 0.0) for d in dists), 4)},
        }
    sums: dict[str, float] = {}
    for d in spoke:
        for label, prob in d.items():
            if label != DC_LEAN_NONE:
                sums[label] = sums.get(label, 0.0) + prob
    total = sum(sums.values()) or 1.0
    dist = {k: round(v / total, 4) for k, v in sums.items()}
    return {"dc_public_lean": max(dist, key=dist.get), "dc_public_lean_probabilities": dist}


def screen_transcript(
    client: JevClient,
    video_id: str,
    segments: Sequence[str],
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> ScreenResult | None:
    """Ask Jev the screening questions about one transcript. ``None`` if it has no text."""
    chunks = chunk_segments(segments, chunk_chars)
    if not chunks:
        return None
    picked = pick_chunks(chunks, max_chunks)
    responses: list[JevResponse] = []
    # Label the usage rows so the cost report can tell the screen apart, per video.
    with llm_call_context(stage="jev_screen", video_id=video_id):
        for index in picked:
            responses.append(client.system_one(state=chunks[index], questions=QUESTIONS))
    tokens = [r.input_tokens for r in responses]
    combined = aggregate(responses)
    return ScreenResult(
        video_id=video_id,
        model=responses[-1].model or client.model,
        chunk_count=len(chunks),
        chunks_screened=len(picked),
        transcript_chars=sum(len(c) for c in chunks),
        input_tokens=sum(tokens) if all(t is not None for t in tokens) else None,
        answers=[
            {"chunk": i, "answers": r.raw.get("answers", {})}
            for i, r in zip(picked, responses)
        ],
        **combined,
    )


def estimate_tokens(
    segments: Sequence[str], *, chunk_chars: int, max_chunks: int
) -> int:
    """Input tokens a screen would send, by the 4-characters-per-token rule of thumb."""
    chunks = chunk_segments(segments, chunk_chars)
    return (
        sum(len(chunks[i]) for i in pick_chunks(chunks, max_chunks)) // CHARS_PER_TOKEN
    )


# Meeting sets that can be screened together (#1029).
COHORTS: dict[str, str] = {
    # Transcripts that name a data center (verbatim passages in data_center_meeting_mention).
    "data-centers": "t.video_id IN (SELECT video_id FROM public.data_center_meeting_mention)",
    # Transcripts linked to the short-term rentals topic (topic_transcript_link, topic 100003).
    "short-term-rentals": "t.video_id IN (SELECT video_id FROM public.topic_transcript_link WHERE topic_id = 100003)",
}


def select_sql(
    *,
    states: Iterable[str],
    jurisdiction_id: str,
    rescreen: bool,
    analyzed_only: bool = False,
    cohorts: Iterable[str] = (),
) -> tuple[str, list[Any]]:
    """Captioned videos to screen, newest first. Already screened with the current
    questions are left out unless ``rescreen``.

    ``analyzed_only`` keeps videos Gemini has already analyzed
    (``policy_analysis_at``) — use this to build a calibrate sample."""
    where = ["t.has_transcript IS TRUE"]
    params: list[Any] = []
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    if state_list:
        where.append("e.state_code = ANY(%s)")
        params.append(state_list)
    if jurisdiction_id:
        where.append("e.jurisdiction_id = %s")
        params.append(jurisdiction_id)
    if analyzed_only:
        where.append("e.policy_analysis_at IS NOT NULL")
    cohort_list = [c for c in cohorts if c]
    if cohort_list:
        where.append("(" + " OR ".join(COHORTS[c] for c in cohort_list) + ")")
    if not rescreen:
        where.append(
            f"NOT EXISTS (SELECT 1 FROM {TABLE} s WHERE s.video_id = t.video_id "
            "AND s.question_version = %s)"
        )
        params.append(QUESTION_VERSION)
    sql = f"""
        SELECT DISTINCT ON (t.video_id)
               t.video_id, t.language, t.is_auto_generated,
               t.segments, t.caption_text_timed, t.raw_text,
               e.published_at
        FROM bronze.bronze_event_youtube_transcript t
        JOIN bronze.bronze_event_youtube e ON e.video_id = t.video_id
        WHERE {" AND ".join(where)}
        ORDER BY t.video_id, e.published_at DESC NULLS LAST
    """
    return (
        f"SELECT * FROM ({sql}) v ORDER BY published_at DESC NULLS LAST LIMIT %s",
        params,
    )


def jev_skip_video_ids(database_url: str, min_decisions_p: float) -> set[str]:
    """Videos whose current screen puts ``has_decisions_p`` below ``min_decisions_p``.

    Unscreened videos, and screens from older question wording, are never returned."""
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [TABLE])
            if cur.fetchone()[0] is None:
                return set()
            # Any screen version: topic-flag bumps must not disable the decisions gate.
            cur.execute(
                f"SELECT video_id FROM {TABLE} "
                "WHERE has_decisions_p IS NOT NULL AND has_decisions_p < %s",
                [min_decisions_p],
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def meeting_keep_p(probabilities: dict[str, Any] | None) -> float | None:
    """``P(government_meeting) + P(town_hall)`` from a screen's kind probabilities.

    Returns ``None`` when neither keep-kind key is present (treat like unscreened)."""
    if not probabilities:
        return None
    total = 0.0
    saw = False
    for key in MEETING_KEEP_KIND_KEYS:
        if key not in probabilities:
            continue
        raw = probabilities.get(key)
        if raw is None:
            continue
        saw = True
        total += float(raw)
    return total if saw else None


def meeting_keep_p_below(keep_p: float | None, min_meeting_p: float) -> bool:
    """True when the keep-score is strictly below the floor.

    ``None`` never skips — same spirit as unscreened."""
    return keep_p is not None and keep_p < min_meeting_p


# Back-compat alias used by older tests / callers.
gov_meeting_p_below = meeting_keep_p_below


OVERRIDE_TABLE = "bronze.bronze_video_meeting_kind_override"
# Overrides that mean "keep for analysis" even when the screen keep-score is low.
KEEP_OVERRIDE_KINDS = ("government_meeting", "town_hall")


def jev_skip_meeting_video_ids(database_url: str, min_meeting_p: float) -> set[str]:
    """Videos whose keep-score ``P(government_meeting)+P(town_hall)`` is below ``min_meeting_p``.

    Unscreened videos, older question wording, and screens missing both keep-kind
    keys are never returned. Human overrides in
    ``bronze.bronze_video_meeting_kind_override`` with kind
    ``government_meeting`` or ``town_hall`` are never skipped (#668)."""
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [TABLE])
            if cur.fetchone()[0] is None:
                return set()
            cur.execute("SELECT to_regclass(%s)", [OVERRIDE_TABLE])
            has_override = cur.fetchone()[0] is not None
            if has_override:
                cur.execute(
                    f"""
                    SELECT s.video_id FROM {TABLE} s
                    WHERE (
                        s.meeting_kind_probabilities ? 'government_meeting'
                        OR s.meeting_kind_probabilities ? 'town_hall'
                      )
                      AND (
                        COALESCE((s.meeting_kind_probabilities->>'government_meeting')::float, 0)
                        + COALESCE((s.meeting_kind_probabilities->>'town_hall')::float, 0)
                      ) < %s
                      AND NOT EXISTS (
                        SELECT 1 FROM {OVERRIDE_TABLE} o
                        WHERE o.video_id = s.video_id
                          AND o.override_kind = ANY(%s)
                      )
                    """,
                    [min_meeting_p, list(KEEP_OVERRIDE_KINDS)],
                )
            else:
                cur.execute(
                    f"""
                    SELECT video_id FROM {TABLE}
                    WHERE (
                        meeting_kind_probabilities ? 'government_meeting'
                        OR meeting_kind_probabilities ? 'town_hall'
                      )
                      AND (
                        COALESCE((meeting_kind_probabilities->>'government_meeting')::float, 0)
                        + COALESCE((meeting_kind_probabilities->>'town_hall')::float, 0)
                      ) < %s
                    """,
                    [min_meeting_p],
                )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


CALIBRATE_THRESHOLDS: tuple[float, ...] = (0.5, 0.6, 0.7)


def calibrate_threshold_table(
    rows: Sequence[tuple[str, float | None]],
    *,
    thresholds: Sequence[float] = CALIBRATE_THRESHOLDS,
) -> list[dict[str, Any]]:
    """Keep/skip counts if ``--skip-jev-meeting-below T`` had gated these analyzed videos.

    Each row is ``(video_id, P(government_meeting)+P(town_hall) | None)``. Null
    keep-score is never a skip. ``false_skip_rate`` is skip/n among this sample.
    """
    n = len(rows)
    out: list[dict[str, Any]] = []
    for t in thresholds:
        skip = sum(1 for _, p in rows if meeting_keep_p_below(p, t))
        out.append(
            {
                "threshold": float(t),
                "n": n,
                "keep": n - skip,
                "skip": skip,
                "false_skip_rate": (skip / n) if n else 0.0,
            }
        )
    return out


def _segment_texts(row: dict[str, Any]) -> list[str]:
    from llm.gemini.transcript_db import normalize_transcript_row

    yt = normalize_transcript_row(row)
    return [s["text"] for s in yt["segments"]] if yt else []


def _database_url(explicit: str) -> str:
    """The warehouse, found the same way as the analysis pipeline's
    (``--database-url`` > ``OPEN_NAVIGATOR_DATABASE_URL`` > its default)."""
    from llm.gemini.analyze_backlog import _resolve_database_url

    return _resolve_database_url(explicit)


def _calibrate_analyzed_rows(
    database_url: str,
    *,
    states: Sequence[str],
    jurisdiction_id: str,
    limit: int,
) -> list[tuple[str, float | None]]:
    """Current-version screens joined to videos Gemini has already analyzed."""
    import psycopg2

    where = [
        "s.question_version = %s",
        "e.policy_analysis_at IS NOT NULL",
    ]
    params: list[Any] = [QUESTION_VERSION]
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    if state_list:
        where.append("e.state_code = ANY(%s)")
        params.append(state_list)
    if jurisdiction_id:
        where.append("e.jurisdiction_id = %s")
        params.append(jurisdiction_id)
    sql = f"""
        SELECT s.video_id,
               CASE
                 WHEN s.meeting_kind_probabilities ? 'government_meeting'
                   OR s.meeting_kind_probabilities ? 'town_hall'
                 THEN COALESCE((s.meeting_kind_probabilities->>'government_meeting')::float, 0)
                    + COALESCE((s.meeting_kind_probabilities->>'town_hall')::float, 0)
                 ELSE NULL
               END AS keep_p
        FROM {TABLE} s
        JOIN bronze.bronze_event_youtube e ON e.video_id = s.video_id
        WHERE {" AND ".join(where)}
        ORDER BY e.policy_analysis_at DESC NULLS LAST
        LIMIT %s
    """
    params.append(limit)
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [TABLE])
            if cur.fetchone()[0] is None:
                return []
            cur.execute(sql, params)
            return [(str(vid), p) for vid, p in cur.fetchall()]
    finally:
        conn.close()


def run_calibrate(args: argparse.Namespace) -> dict[str, Any]:
    """Print keep/skip rates at candidate T values; does not call Jev."""
    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    rows = _calibrate_analyzed_rows(
        database_url,
        states=states,
        jurisdiction_id=args.jurisdiction_id or "",
        limit=args.limit,
    )
    table = calibrate_threshold_table(rows)
    logger.info(
        "Calibrate on {:,} already-analyzed video(s) with current Jev screens "
        "(questions {}); keep-score = P(government_meeting)+P(town_hall)",
        len(rows),
        QUESTION_VERSION,
    )
    if not rows:
        logger.warning(
            "No joined rows — screen some analyzed videos first, or widen --state/--limit."
        )
        return {"n": 0, "thresholds": table}
    for row in table:
        logger.success(
            "T={threshold:.2f}: keep {keep:,} / skip {skip:,} "
            "(false-skip rate {false_skip_rate:.1%} of this sample)",
            **row,
        )
    logger.info(
        "Pick T from the table, record it under Chosen threshold in "
        "web_docs/docs/development/jev-meeting-kind-gate.md, then submit with "
        "--skip-jev-meeting-below T."
    )
    return {"n": len(rows), "thresholds": table}


def run(args: argparse.Namespace) -> dict[str, Any]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    from llm.usage.prices import load_prices, model_price

    if getattr(args, "calibrate", False):
        return run_calibrate(args)

    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    sql, params = select_sql(
        states=states,
        jurisdiction_id=args.jurisdiction_id,
        rescreen=args.rescreen,
        analyzed_only=bool(getattr(args, "analyzed_only", False)),
        cohorts=[c for part in (getattr(args, "cohort", None) or []) for c in part.split(",")],
    )

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
            cur.execute(ALTER_TOPIC_COLUMNS_SQL)
        conn.commit()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, [*params, args.limit])
            rows = cur.fetchall()
    finally:
        conn.close()
    logger.info(
        "{:,} transcript(s) to screen (questions {})", len(rows), QUESTION_VERSION
    )

    summary = {
        "selected": len(rows),
        "screened": 0,
        "empty": 0,
        "failed": 0,
        "input_tokens": 0,
    }
    if args.dry_run:
        est = sum(
            estimate_tokens(
                _segment_texts(r),
                chunk_chars=args.chunk_chars,
                max_chunks=args.max_chunks,
            )
            for r in rows
        )
        rate = model_price("jev-", "interactive", load_prices())
        cost = (
            f"${est * rate['input_usd_per_1m'] / 1_000_000:,.4f}"
            if rate
            else "no price on file"
        )
        logger.success(
            "Dry run: ~{:,} input tokens, about {} at Jev's listed price. Nothing sent.",
            est,
            cost,
        )
        summary["estimated_input_tokens"] = est
        return summary

    with JevClient(model=args.model or None) as client:
        conn = psycopg2.connect(database_url)
        try:
            for i, row in enumerate(rows, 1):
                vid = row["video_id"]
                try:
                    result = screen_transcript(
                        client,
                        vid,
                        _segment_texts(row),
                        chunk_chars=args.chunk_chars,
                        max_chunks=args.max_chunks,
                    )
                except JevError as exc:
                    summary["failed"] += 1
                    logger.warning("[{}/{}] {}: {}", i, len(rows), vid, exc)
                    if exc.status_code in (401, 403):
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
                    "[{}/{}] {} {} decisions={:.2f} data_center={:.2f} ({} of {} chunks)",
                    i,
                    len(rows),
                    vid,
                    result.meeting_kind,
                    result.has_decisions_p or 0.0,
                    result.mentions_data_center_p or 0.0,
                    result.chunks_screened,
                    result.chunk_count,
                )
        finally:
            conn.close()
    logger.success(
        "Screened {screened:,}, empty {empty:,}, failed {failed:,}; {input_tokens:,} input tokens".format(
            **summary
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Screen meeting transcripts with TypeSafe's Jev before Gemini analysis."
    )
    p.add_argument(
        "--state",
        action="append",
        default=None,
        help="State code(s), repeatable or comma-separated",
    )
    p.add_argument("--jurisdiction-id", default="")
    p.add_argument(
        "--cohort",
        action="append",
        default=None,
        help=f"Only these meeting sets (repeatable or comma-separated): {', '.join(COHORTS)} (#1029)",
    )
    p.add_argument(
        "--limit", type=int, default=100, help="Most videos to screen (default 100)"
    )
    p.add_argument(
        "--rescreen", action="store_true", help="Screen again even if already screened"
    )
    p.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS)
    p.add_argument("--max-chunks", type=int, default=DEFAULT_MAX_CHUNKS)
    p.add_argument(
        "--model", default="", help="Jev model (default TYPESAFE_MODEL or jev-latest)"
    )
    p.add_argument(
        "--database-url",
        default="",
        help="Warehouse DSN (default: as the analysis pipeline resolves it)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Count and estimate tokens; send nothing"
    )
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="Join current screens to already-analyzed videos and report "
        "keep/skip rates at P(government_meeting)+P(town_hall) thresholds; "
        "does not call Jev",
    )
    p.add_argument(
        "--analyzed-only",
        action="store_true",
        help="Only screen videos that already have Gemini analysis "
        "(policy_analysis_at); for building a calibrate sample",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except JevError as exc:
        logger.error("{}", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
