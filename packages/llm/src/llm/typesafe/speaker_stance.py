"""Each public speaker's own side and heat on a topic, read by Jev (#1391).

The free cue rules (#1386, ``stance_shape``) leave most public speakers ``unclear`` or ``concerns_only``: captions
rarely say "I support" or "I oppose" in so many words. This module asks Jev, once per (speaker, topic), about the
passages of that speaker's OWN turn text that name the topic:

- ``side`` (Choice): ``for`` / ``against`` the topic's concrete local action, ``concerns_only`` (concerns or questions,
  no side), ``no_position`` (on the topic, no side and no concern), ``off_topic`` (a passing mention or another
  meaning of the keyword);
- ``heat_2`` .. ``heat_5`` (Noul): a ladder of yes/no thresholds; heat is 1 plus the number of consecutive thresholds
  Jev judges true (P >= 0.5), so it is 1-5.

A speaker is asked only about the topic(s) their own words match (the topic's keyword phrases), never every topic.
Possible minors and speakers at school-board meetings are never sent (AGENTS.md, Privacy). Jev returns probabilities,
never text; nothing here names anyone: rows are keyed by ``meeting_speaker_id`` (meeting + name key, never linked
across meetings).

Readings land in ``bronze.bronze_speaker_topic_stance_jev``, one row per (meeting_speaker_id, topic_id,
question_version), written as each answer arrives. A run skips rows already read at the topic's current question
version, so a stopped run (budget, out of credits) resumes with the same command and pays nothing twice.

Topics run in :data:`PRIORITY` order (data centers first; the score is documented in
``web_docs/docs/development/speaker-stance-classifier.md``); inside a topic the hottest meetings go first
(:func:`meeting_heat_scores`, a free estimate), 2026 breaking ties.

Usage (paid: run only on the owner's go-ahead; read usage before and after, AGENTS.md)::

    python -m llm.typesafe.speaker_stance --topic all --dry-run
    python -m llm.typesafe.speaker_stance --topic all --max-usd 18
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from loguru import logger

from llm.typesafe.client import JevClient, JevError, JevResponse, choice, noul
from llm.typesafe.topic_lean import TOPICS as MEETING_TOPICS
from llm.typesafe.topic_lean import keyword_pattern
from llm.usage.calls import llm_call_context

TABLE = "bronze.bronze_speaker_topic_stance_jev"
#: Bumped when the passage builder changes (window size, cap). Stored per row, not hashed: a new builder alone does not
#: force a re-read.
STATE_VERSION = "speaker_state/1"
WINDOW_CHARS = 700
MAX_STATE_CHARS = 2800
SIDES: tuple[str, ...] = ("for", "against", "concerns_only", "no_position", "off_topic")
HEAT_LEVELS: tuple[int, ...] = (2, 3, 4, 5)
#: A side is served only at or above this probability (calibrated on the gold set, speaker-stance-classifier.md).
MIN_SIDE_CONFIDENCE = 0.8
#: Heat is served at or above this margin (each ladder decision at P >= 0.65 or <= 0.35).
MIN_HEAT_CONFIDENCE = 0.65
#: Payment / auth statuses that stop a run at once (no retry loop).
STOP_STATUSES = frozenset({401, 402, 403})


@dataclass(frozen=True)
class SpeakerTopic:
    """What being for or against means for one topic, at speaker grain."""

    slug: str
    topic_id: int
    #: The concrete local action a speaker is for or against.
    subject: str
    #: A short name for the item ("the data center").
    item: str
    #: Other senses of the keywords, and passing mentions, that are off topic.
    excludes: str
    #: Who is for and who is against, in plain examples.
    sides: str
    #: The keyword phrases a speaker's own words must contain. ``None``: the curated topic's seed keywords
    #: (``public.civicsearch_topic.keyword_stats``, the phrases behind ``meeting_comment.topic_ids``).
    keywords: tuple[str, ...] | None = None


def _from_meeting(slug: str) -> SpeakerTopic:
    t = MEETING_TOPICS[slug]
    return SpeakerTopic(slug=t.slug, topic_id=t.topic_id, subject=t.subject, item=t.item, excludes=t.excludes,
                        sides=t.sides)


_FLUORIDE = MEETING_TOPICS["water-fluoridation"]

TOPICS: dict[str, SpeakerTopic] = {
    "data-centers": SpeakerTopic(
        slug="data-centers",
        topic_id=100001,
        subject=(
            "a large data center: approving, rezoning land for, giving incentives to or building a data center "
            "facility (a campus of computer servers, often called a hyperscale or AI data center)"
        ),
        item="data center",
        excludes=(
            "An office server room, a government's own IT systems or a records 'data center', and a passing mention "
            "of data centers in a list of businesses, do not count."
        ),
        sides=(
            "Residents asking the body to deny, pause, limit or move a data center, or a moratorium on them, are "
            "against. Residents backing it for jobs, taxes or investment are for. Worries about water, power, noise or "
            "taxes without saying which way the body should decide are concerns only."
        ),
    ),
    "water-fluoridation": SpeakerTopic(
        slug="water-fluoridation",
        topic_id=100002,
        subject="community water fluoridation: keeping, starting or restoring fluoride in the public drinking water",
        item="fluoridation",
        excludes=_FLUORIDE.excludes,
        sides=(
            "People asking to keep or add fluoride (often dentists, doctors, parents) are for. People asking to stop, "
            "end or not start fluoridating are against."
        ),
    ),
    "short-term-rentals": _from_meeting("short-term-rentals"),
    "license-plate-readers": _from_meeting("license-plate-readers"),
    "guns": _from_meeting("guns"),
    "pickleball": _from_meeting("pickleball"),
    "traffic-safety": SpeakerTopic(
        slug="traffic-safety",
        topic_id=100010,
        subject=(
            "traffic calming and speed enforcement on local streets: speed humps or bumps, lower speed limits, "
            "speed or red-light cameras, crosswalks, stop signs or other changes that slow traffic"
        ),
        item="traffic calming measure",
        excludes=(
            "A traffic crash or crime report with no ask about slowing traffic, a road repaving schedule, and parking "
            "rules alone do not count."
        ),
        sides=(
            "Residents asking for speed humps, lower limits, cameras, crosswalks or stop signs are for. Residents "
            "objecting to them (speed cameras as a cash grab, humps that slow fire trucks, removing a stop sign) are "
            "against."
        ),
    ),
    "police-staffing": SpeakerTopic(
        slug="police-staffing",
        topic_id=100011,
        subject="more police funding or staffing: a bigger police budget, more officers, or higher police pay",
        item="police funding",
        excludes=(
            "A report of a crime, thanks to an officer, or a complaint about one incident, with no ask about the "
            "police budget, staffing or pay, does not count."
        ),
        sides=(
            "Residents asking to hire more officers, fund the police or raise their pay are for. Residents asking to "
            "cut or move police money to other services (defund, reallocate) are against."
        ),
    ),
    "parks-funding": SpeakerTopic(
        slug="parks-funding",
        topic_id=100016,
        subject=(
            "spending on parks and recreation: a park bond or levy, renovating or building parks or a recreation "
            "center, or the parks budget"
        ),
        item="parks spending",
        excludes="Parking, a business park, or a person named Park do not count.",
        sides=(
            "Residents asking the body to fund, build or fix parks or recreation centers are for. Residents objecting "
            "to the cost, the tax or bond for it, or to a park project, are against."
        ),
    ),
    "homelessness-and-shelters": SpeakerTopic(
        slug="homelessness-and-shelters",
        topic_id=100018,
        subject=(
            "shelters, services or housing for homeless people in the community: opening or funding a shelter, "
            "warming center, services site or supportive housing"
        ),
        item="homeless shelter or service",
        excludes="A homeless count or report with no ask about a shelter, service or housing does not count.",
        sides=(
            "Residents asking for a shelter, services or housing for homeless people are for. Residents objecting to "
            "a shelter or service site near them, or asking for clearing encampments instead of services, are against."
        ),
    ),
    "immigration-and-sanctuary": SpeakerTopic(
        slug="immigration-and-sanctuary",
        topic_id=100019,
        subject=(
            "limiting local cooperation with federal immigration enforcement: sanctuary or welcoming policies, "
            "refusing ICE detainers or 287(g) agreements"
        ),
        item="sanctuary policy",
        excludes="Immigration mentioned only as national news, with no local policy at issue, does not count.",
        sides=(
            "Residents asking the body to protect immigrants, adopt or keep a sanctuary policy, or end cooperation with "
            "ICE are for. Residents asking for cooperation with ICE, a 287(g) agreement or an end to a sanctuary policy "
            "are against."
        ),
    ),
    "bike-lanes": SpeakerTopic(
        slug="bike-lanes",
        topic_id=100020,
        subject="building or keeping bike lanes, protected bike lanes or bike paths on local streets",
        item="bike lane",
        excludes="Motorcycles, exercise bikes, and a bike race or event with no lane or path at issue do not count.",
        sides=(
            "Cyclists and residents asking for lanes or paths are for. Residents or businesses objecting to losing "
            "parking or traffic lanes, or asking to remove lanes, are against."
        ),
    ),
    "local-taxation": SpeakerTopic(
        slug="local-taxation",
        topic_id=74,
        subject=(
            "raising local taxes or fees: a higher property tax rate or millage, a tax levy or sales tax increase, "
            "or new local fees"
        ),
        item="tax increase",
        excludes="A tax credit, tax abatement for a company, or a state or federal tax alone does not count.",
        sides=(
            "Residents backing a levy, tax or fee increase (for schools, roads, police, services) are for. Residents "
            "objecting to higher taxes or fees, or asking for a cut, are against."
        ),
        keywords=(
            "property tax", "property taxes", "millage", "mill levy", "tax levy", "levy", "tax increase", "tax hike",
            "raise taxes", "raising taxes", "raise our taxes", "tax rate", "sales tax", "higher taxes",
        ),
    ),
    "affordable-housing": SpeakerTopic(
        slug="affordable-housing",
        topic_id=83,
        subject=(
            "an affordable housing development or policy: approving low-income, workforce or income-restricted "
            "housing, or rules that require or fund it"
        ),
        item="affordable housing project",
        excludes="A home's market price or a rent complaint with no project or policy at issue does not count.",
        sides=(
            "Residents asking the body to approve or fund affordable housing are for. Residents objecting to an "
            "affordable housing project near them (density, traffic, property values) are against."
        ),
        keywords=(
            "affordable housing", "affordable units", "low-income housing", "low income housing", "workforce housing",
            "income-restricted", "income restricted", "inclusionary", "section 8", "subsidized housing",
        ),
    ),
    "zoning-regulations": SpeakerTopic(
        slug="zoning-regulations",
        topic_id=77,
        subject=(
            "rezoning or zoning changes that allow denser housing or development: apartments, townhomes, duplexes, "
            "accessory dwellings or higher density"
        ),
        item="rezoning",
        excludes="A zoning change for a single-family home, a sign, or a business use with no added density does not count.",
        sides=(
            "Residents asking the body to allow more homes, apartments or density are for. Residents objecting to "
            "density, apartments or a rezoning near them are against."
        ),
        keywords=(
            "rezoning", "rezone", "upzoning", "high density", "high-density", "higher density", "density",
            "multifamily", "multi-family", "apartment complex", "apartments", "townhomes", "townhouses", "duplexes",
            "accessory dwelling", "adus",
        ),
    ),
    "renewable-energy": SpeakerTopic(
        slug="renewable-energy",
        topic_id=90,
        subject="approving local solar or wind energy projects: solar farms, wind turbines or battery storage sites",
        item="solar or wind project",
        excludes="Rooftop solar on one home, electric vehicles alone, or a utility bill complaint does not count.",
        sides=(
            "Residents and landowners backing a solar farm, wind project or battery site are for. Neighbors objecting "
            "to one (farmland, views, fire risk, property values) or asking for a moratorium are against."
        ),
        keywords=(
            "solar farm", "solar farms", "solar project", "solar projects", "solar facility", "solar array",
            "solar energy", "solar panels", "utility-scale solar", "wind farm", "wind farms", "wind turbine",
            "wind turbines", "battery storage",
        ),
    ),
    "surveillance-cameras": SpeakerTopic(
        slug="surveillance-cameras",
        topic_id=28,
        subject="expanding city surveillance cameras: new or more security or surveillance cameras in public places",
        item="surveillance camera",
        excludes="Body cameras alone, a meeting's video stream, and a photo or video someone took do not count.",
        sides=(
            "Residents asking for more cameras for safety are for. Residents raising privacy or surveillance "
            "objections, or asking to remove cameras or limit their use, are against."
        ),
        keywords=(
            "surveillance camera", "surveillance cameras", "security camera", "security cameras", "surveillance",
            "facial recognition", "camera system", "cameras",
        ),
    ),
    "public-transit": SpeakerTopic(
        slug="public-transit",
        topic_id=55,
        subject="expanding or funding public transit: more bus routes or service, light rail, or transit funding",
        item="transit service",
        excludes="School buses, a tour bus, or a road project with no transit at issue does not count.",
        sides=(
            "Riders and residents asking for more or better bus or rail service are for. Residents objecting to a "
            "transit project, its cost or tax, or a route or stop near them are against."
        ),
        keywords=(
            "public transit", "public transportation", "bus service", "bus route", "bus routes", "bus stop",
            "bus stops", "light rail", "commuter rail", "paratransit", "bus rapid transit", "transit",
        ),
    ),
    "alcohol-licensing": SpeakerTopic(
        slug="alcohol-licensing",
        topic_id=14,
        subject="approving a liquor license or allowing alcohol sales: a bar, liquor store, or beer and wine sales",
        item="liquor license",
        excludes="Drunk driving or an arrest report with no license or sales rule at issue does not count.",
        sides=(
            "Owners and residents backing the license or alcohol sales are for. Neighbors or churches objecting to a "
            "bar or liquor store near them, or to allowing sales, are against."
        ),
        keywords=(
            "liquor license", "liquor licenses", "alcohol license", "beer and wine", "alcohol sales", "liquor store",
            "package store", "sell alcohol", "serve alcohol", "alcoholic beverage", "alcoholic beverages",
        ),
    ),
}

#: Run order (#1391, owner: "sort by the most trending topics with heat or different opinions"). Data centers first,
#: then by the equal-weight score of normalized YoY rise + contention + AI heat (``speaker_stance_priority``), recorded
#: with its numbers in the decision page. A topic missing here runs last, in TOPICS order.
PRIORITY: tuple[str, ...] = (
    "data-centers", "license-plate-readers", "short-term-rentals", "immigration-and-sanctuary", "police-staffing",
    "guns", "surveillance-cameras", "zoning-regulations", "homelessness-and-shelters", "affordable-housing",
    "pickleball", "water-fluoridation", "alcohol-licensing", "bike-lanes", "traffic-safety", "local-taxation",
    "renewable-energy", "public-transit", "parks-funding",
)


#: Topics whose gold check did not pass (speaker_stance_gold: too few clear items, or too many wrong sides served);
#: ``--topic all`` skips them until more hand labels show they work. Named explicitly, they still run.
HELD: frozenset[str] = frozenset({
    "bike-lanes", "local-taxation", "parks-funding", "public-transit", "traffic-safety", "zoning-regulations",
})


def side_criteria(topic: SpeakerTopic) -> dict[str, str]:
    return {
        "for": f"The speaker said they are for {topic.subject}, or asked the body to approve or move it forward",
        "against": f"The speaker said they are against {topic.subject}, or asked the body to deny, stop or limit it",
        "concerns_only": (
            f"The speaker raised concerns or asked questions about the {topic.item} (cost, noise, water, traffic, "
            "safety, process) without saying whether the body should approve or reject it"
        ),
        "no_position": (
            f"The speaker talked about the {topic.item} but took no side and raised no concern (facts, thanks, an "
            "announcement)"
        ),
        "off_topic": f"The speaker did not talk about {topic.subject}: a passing mention or another meaning of the words",
    }


def heat_questions() -> dict[str, dict[str, Any]]:
    return {
        "heat_2": noul("The speaker sounds more than calm and matter-of-fact: concerned, emphatic or frustrated"),
        "heat_3": noul("The speaker is clearly upset or passionate: strong words, urgency, pleading or repeated emphasis"),
        "heat_4": noul("The speaker is angry or alarmed: accuses officials, demands action or warns of serious harm"),
        "heat_5": noul(
            "The speaker is furious or hostile: shouting, insults, threats to vote officials out or to sue, or the "
            "chair has to stop them"
        ),
    }


def speaker_questions(topic: SpeakerTopic) -> dict[str, dict[str, Any]]:
    """The side question for one topic plus the heat ladder, asked in one request."""
    instructions = (
        "This is what one member of the public said during public comment at a local government meeting. Which best "
        f"describes this speaker's own position on {topic.subject}? {topic.excludes} {topic.sides}"
    )
    return {"side": choice(instructions, side_criteria(topic)), **heat_questions()}


def question_version(topic: SpeakerTopic) -> str:
    """Changes whenever a topic's question wording changes, so a rewording is read again."""
    return hashlib.sha256(json.dumps(speaker_questions(topic), sort_keys=True).encode()).hexdigest()[:12]


def build_state(text: str, pattern: re.Pattern[str] | None, *, window: int = WINDOW_CHARS,
                max_chars: int = MAX_STATE_CHARS) -> str | None:
    """The passages of a speaker's own text that name the topic: ``window`` characters each side of every keyword hit,
    merged where they overlap, the windows with the most hits kept up to ``max_chars``, in speech order. ``None`` when
    no keyword is in the text."""
    if not text or pattern is None:
        return None
    hits = [m.start() for m in pattern.finditer(text)]
    if not hits:
        return None
    spans: list[list[int]] = []
    for h in hits:
        lo, hi = max(0, h - window), min(len(text), h + window)
        if spans and lo <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], hi)
            spans[-1][2] += 1
        else:
            spans.append([lo, hi, 1])
    keep: list[list[int]] = []
    used = 0
    for s in sorted(spans, key=lambda s: (-s[2], s[0])):
        size = s[1] - s[0]
        if keep and used + size > max_chars:
            continue
        if not keep and size > max_chars:  # one long merged span: centre it on its first hit
            first = next(h for h in hits if s[0] <= h < s[1])
            lo = max(s[0], first - max_chars // 2)
            s = [lo, min(s[1], lo + max_chars), s[2]]
            size = s[1] - s[0]
        keep.append(s)
        used += size
    parts = []
    for lo, hi, _ in sorted(keep):
        # widen to word boundaries so no word is cut
        while lo > 0 and not text[lo - 1].isspace():
            lo -= 1
        while hi < len(text) and not text[hi].isspace():
            hi += 1
        parts.append(text[lo:hi].strip())
    return " ... ".join(parts)


def heat_from(probs: dict[str, float | None]) -> tuple[int, float]:
    """(heat 1-5, confidence) from P(heat >= k). Heat climbs while each threshold is judged true (P >= 0.5); the
    confidence is the weakest of the decisions taken (the climbed thresholds and the first one refused)."""
    heat, margins = 1, []
    for k in HEAT_LEVELS:
        p = probs.get(f"heat_{k}")
        if p is None:
            break
        margins.append(max(p, 1 - p))
        if p >= 0.5:
            heat = k
        else:
            break
    return heat, round(min(margins), 3) if margins else 0.0


@dataclass(frozen=True)
class SpeakerReading:
    meeting_speaker_id: str
    video_id: str
    topic: SpeakerTopic
    model: str
    side: str | None
    side_probabilities: dict[str, float]
    side_confidence: float | None
    heat: int
    heat_probabilities: dict[str, float | None]
    heat_confidence: float
    input_chars: int
    input_tokens: int | None
    answers: dict[str, Any]

    def row(self) -> dict[str, Any]:
        return {
            "meeting_speaker_id": self.meeting_speaker_id,
            "topic_id": self.topic.topic_id,
            "question_version": question_version(self.topic),
            "video_id": self.video_id,
            "topic_slug": self.topic.slug,
            "model": self.model,
            "state_version": STATE_VERSION,
            "side": self.side,
            "side_probabilities": json.dumps(self.side_probabilities),
            "side_confidence": self.side_confidence,
            "heat": self.heat,
            "heat_probabilities": json.dumps(self.heat_probabilities),
            "heat_confidence": self.heat_confidence,
            "input_chars": self.input_chars,
            "input_tokens": self.input_tokens,
            "answers": json.dumps(self.answers),
            "screened_at": datetime.now(UTC),
        }


def read_response(resp: JevResponse, *, speaker_id: str, video_id: str, topic: SpeakerTopic,
                  state: str) -> SpeakerReading:
    side_ans = resp.answers.get("side")
    probs = dict(side_ans.probabilities) if side_ans else {}
    side = (side_ans.choice if side_ans and side_ans.choice else (max(probs, key=probs.get) if probs else None))
    conf = probs.get(side) if side else None
    heat_p = {f"heat_{k}": (resp.answers[f"heat_{k}"].noul if f"heat_{k}" in resp.answers else None) for k in HEAT_LEVELS}
    heat, heat_conf = heat_from(heat_p)
    return SpeakerReading(
        meeting_speaker_id=speaker_id, video_id=video_id, topic=topic, model=resp.model or "",
        side=side, side_probabilities=probs, side_confidence=round(conf, 4) if conf is not None else None,
        heat=heat, heat_probabilities=heat_p, heat_confidence=heat_conf,
        input_chars=len(state), input_tokens=resp.input_tokens, answers=resp.raw.get("answers", {}),
    )


def ask(client: JevClient, *, speaker_id: str, video_id: str, topic: SpeakerTopic, state: str) -> SpeakerReading:
    with llm_call_context(stage=f"jev_speaker_stance:{topic.slug}", video_id=video_id):
        resp = client.system_one(state=state, questions=speaker_questions(topic))
    return read_response(resp, speaker_id=speaker_id, video_id=video_id, topic=topic, state=state)


CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    meeting_speaker_id   text NOT NULL,
    topic_id             integer NOT NULL,
    question_version     text NOT NULL,
    video_id             text NOT NULL,
    topic_slug           text NOT NULL,
    model                text NOT NULL,
    state_version        text NOT NULL,
    side                 text,
    side_probabilities   jsonb,
    side_confidence      numeric(6, 4),
    heat                 integer,
    heat_probabilities   jsonb,
    heat_confidence      numeric(6, 4),
    input_chars          integer NOT NULL,
    input_tokens         integer,
    answers              jsonb NOT NULL,
    screened_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meeting_speaker_id, topic_id, question_version)
)
"""

_COLS = ("meeting_speaker_id", "topic_id", "question_version", "video_id", "topic_slug", "model", "state_version",
         "side", "side_probabilities", "side_confidence", "heat", "heat_probabilities", "heat_confidence",
         "input_chars", "input_tokens", "answers", "screened_at")
UPSERT_SQL = (
    f"INSERT INTO {TABLE} ({', '.join(_COLS)}) VALUES ({', '.join(f'%({c})s' for c in _COLS)}) "
    "ON CONFLICT (meeting_speaker_id, topic_id, question_version) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLS[3:])
)

# Public speakers who may be sent: public comment, not a possible minor, not at a school-board meeting (the same
# school-board rule as int_meeting_comment__turns). Their own segment text, in speech order.
SCHOOL_BOARD_SQL = (
    "(coalesce(m.jurisdiction_name, '') ~* '(school|\\misd\\M|\\musd\\M|board\\s+of\\s+ed)' "
    "or coalesce(m.meeting_title, '') ~* '(schools?\\s+board|school\\s+district|school\\s+committee|board\\s+of\\s+ed"
    "|\\mboe\\M|\\musd\\M|\\misd\\M|board\\s+of\\s+trustees.*school|student)')"
)
SPEAKERS_SQL = f"""
    SELECT p.meeting_speaker_id, p.video_id, p.meeting_date,
           string_agg(f.comment_text, ' ' ORDER BY t.comment_index) AS txt
    FROM gold.meeting_speaker_position p
    JOIN gold.segmented_meeting m ON m.video_id = p.video_id
    JOIN intermediate.int_meeting_comment__turns t ON t.meeting_speaker_id = p.meeting_speaker_id
    JOIN intermediate.int_meeting_comment__flags f ON f.comment_segment_id = t.comment_segment_id
    WHERE p.is_public_comment AND NOT p.possible_minor AND NOT {SCHOOL_BOARD_SQL}
    GROUP BY p.meeting_speaker_id, p.video_id, p.meeting_date
"""


@dataclass(frozen=True)
class Job:
    meeting_speaker_id: str
    video_id: str
    meeting_date: date | None
    topic: SpeakerTopic
    state: str


# Owner (2026-11-27): "We should prioritize meetings with a lot of heat." A free pre-run estimate per meeting, four
# parts each scaled 0-1 and summed with equal weights (:func:`meeting_heat_scores`):
#   ai_heat     the AI meeting analysis's highest comment heat (gold.public_comment, 1-5 -> 0-1); 0 when none;
#   speakers    public speakers at the meeting, ln(1 + n) / ln(1 + max);
#   contested   per topic: topic_meeting_lean says both sides spoke (mixed) or officials sided against the public;
#   chair_cues  the chair keeping order in the transcript (CHAIR_CUES: point of order, out of order, time is up,
#               please address the board, recess), ln(1 + n) / ln(1 + the 99th percentile), capped at 1.
CHAIR_CUES = (
    "point of order|order please|please address (the|your comments to the) (board|council|commission|chair)|"
    "your time is up|time has expired|time is expired|times up|out of order|we will (take a )?(short )?recess|"
    "take a (short |brief )?recess"
)
MEETING_HEAT_SQL = f"""
    WITH m AS (SELECT video_id FROM gold.segmented_meeting),
    ai AS (SELECT video_id, max(heat) AS ai_heat FROM gold.public_comment WHERE heat BETWEEN 1 AND 5 GROUP BY video_id),
    sp AS (SELECT video_id, count(*) AS speakers FROM gold.meeting_speaker_position WHERE is_public_comment
           GROUP BY video_id),
    cues AS (SELECT t.video_id, max(regexp_count(lower(coalesce(t.raw_text, '')), '{CHAIR_CUES}')) AS chair_cues
             FROM bronze.bronze_event_youtube_transcript t
             WHERE t.has_transcript AND t.video_id IN (SELECT video_id FROM m) GROUP BY t.video_id)
    SELECT m.video_id, ai.ai_heat, coalesce(sp.speakers, 0), coalesce(cues.chair_cues, 0)
    FROM m LEFT JOIN ai USING (video_id) LEFT JOIN sp USING (video_id) LEFT JOIN cues USING (video_id)
"""
CONTESTED_SQL = """
    SELECT video_id, topic_id
    FROM public.topic_meeting_lean
    WHERE public_lean = 'mixed'
       OR (public_lean IN ('mostly_supportive', 'mostly_opposed') AND official_lean IN ('mostly_supportive', 'mostly_opposed')
           AND official_lean <> public_lean)
"""


def meeting_heat_scores(rows: Iterable[tuple[str, int | None, int, int]],
                        contested: set[tuple[str, int]], topic_ids: Iterable[int]) -> dict[tuple[str, int], float]:
    """(video_id, topic_id) -> the pre-run heat estimate (0-4), for every meeting and topic given."""
    import math

    rows = list(rows)
    max_sp = max((r[2] for r in rows), default=0)
    cues = sorted(r[3] for r in rows)
    p99 = cues[int(0.99 * (len(cues) - 1))] if cues else 0
    base: dict[str, float] = {}
    for vid, ai, sp, cue in rows:
        a = (ai - 1) / 4 if ai else 0.0
        s = math.log1p(sp) / math.log1p(max_sp) if max_sp else 0.0
        c = min(1.0, math.log1p(cue) / math.log1p(p99)) if p99 else 0.0
        base[vid] = a + s + c
    tids = list(topic_ids)
    return {(vid, t): b + (1.0 if (vid, t) in contested else 0.0) for vid, b in base.items() for t in tids}


def strict_pattern(keywords: Sequence[str]) -> re.Pattern[str] | None:
    """Like :func:`topic_lean.keyword_pattern` (space or hyphen match either), but whole words only, with an optional
    plural: "transit" never matches "transition". Used for the reframed topics' own phrases."""
    parts = []
    for kw in keywords:
        words = [re.escape(w) for w in re.split(r"[\s-]+", str(kw).strip().lower()) if w]
        if words:
            parts.append(r"\b" + r"[\s-]+".join(words) + r"(?:s|es)?\b")
    if not parts:
        return None
    return re.compile("|".join(sorted(set(parts), key=len, reverse=True)), re.IGNORECASE)


def topic_patterns(conn: Any, topics: Sequence[SpeakerTopic]) -> dict[str, re.Pattern[str] | None]:
    out: dict[str, re.Pattern[str] | None] = {}
    with conn.cursor() as cur:
        for t in topics:
            if t.keywords is not None:
                out[t.slug] = strict_pattern(t.keywords)
                continue
            cur.execute("SELECT keyword_stats FROM public.civicsearch_topic WHERE topic_id = %s", [t.topic_id])
            row = cur.fetchone()
            stats = row[0] if row else None
            if isinstance(stats, str):
                stats = json.loads(stats)
            words = list(stats) if isinstance(stats, (dict, list)) else []
            out[t.slug] = keyword_pattern([str(w) for w in words])
    return out


def ordered_topics(topics: Iterable[SpeakerTopic]) -> list[SpeakerTopic]:
    rank = {slug: i for i, slug in enumerate(PRIORITY)}
    return sorted(topics, key=lambda t: (rank.get(t.slug, len(rank)), list(TOPICS).index(t.slug)))


def build_jobs(speakers: Iterable[tuple[str, str, date | None, str]], topics: Sequence[SpeakerTopic],
               patterns: dict[str, re.Pattern[str] | None], done: set[tuple[str, int, str]],
               *, year: int = 2026, heat: dict[tuple[str, int], float] | None = None,
               ) -> tuple[list[Job], dict[str, dict[str, int]]]:
    """Every (speaker, topic) to read, in run order: topics by PRIORITY; inside a topic the hottest meetings first
    (``heat``, :func:`meeting_heat_scores`), ``year``-and-later meetings breaking ties, then newest first. Rows already
    read at the topic's current question version are skipped and counted."""
    versions = {t.slug: question_version(t) for t in topics}
    per_topic: dict[str, list[Job]] = {t.slug: [] for t in topics}
    stats = {t.slug: {"matched": 0, "done": 0, "todo": 0, "todo_chars": 0} for t in topics}
    for sid, vid, mdate, txt in speakers:
        for t in topics:
            state = build_state(txt or "", patterns.get(t.slug))
            if state is None:
                continue
            st = stats[t.slug]
            st["matched"] += 1
            if (sid, t.topic_id, versions[t.slug]) in done:
                st["done"] += 1
                continue
            st["todo"] += 1
            st["todo_chars"] += len(state)
            per_topic[t.slug].append(Job(sid, vid, mdate, t, state))
    jobs: list[Job] = []
    for t in ordered_topics(topics):
        js = per_topic[t.slug]
        hs = heat or {}
        js.sort(key=lambda j: (-round(hs.get((j.video_id, j.topic.topic_id), 0.0), 6),
                               not (j.meeting_date and j.meeting_date.year >= year),
                               -(j.meeting_date.toordinal() if j.meeting_date else 0), j.meeting_speaker_id))
        jobs.extend(js)
    return jobs, stats


#: Jev's tokens per request beyond the passage (the questions), measured on the gold run (speaker-stance-classifier.md).
QUESTION_TOKENS = 700
CHARS_PER_TOKEN = 4


def estimate_usd(chars: int, requests: int, rate_per_1m: float) -> float:
    return (chars / CHARS_PER_TOKEN + requests * QUESTION_TOKENS) * rate_per_1m / 1_000_000


def resolve_topics(arg: str) -> list[SpeakerTopic]:
    slugs = [s for s in TOPICS if s not in HELD] if arg.strip() == "all" else [s.strip() for s in arg.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in TOPICS]
    if unknown or not slugs:
        raise SystemExit(f"Unknown topic(s): {', '.join(unknown) or arg!r}. Choose from: {', '.join(TOPICS)}, or all")
    return [TOPICS[s] for s in slugs]


def _done_keys(conn: Any) -> set[tuple[str, int, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", [TABLE])
        if not cur.fetchone()[0]:
            return set()
        cur.execute(f"SELECT meeting_speaker_id, topic_id, question_version FROM {TABLE}")
        return {(a, int(b), c) for a, b, c in cur.fetchall()}


def load_speakers(conn: Any) -> list[tuple[str, str, date | None, str]]:
    with conn.cursor(name="speaker_stance_speakers") as cur:
        cur.itersize = 2000
        cur.execute(SPEAKERS_SQL)
        return [(r[0], r[1], r[2], r[3]) for r in cur]


def run(args: argparse.Namespace) -> dict[str, Any]:
    import psycopg2

    from llm.typesafe.screen_transcripts import _database_url
    from llm.usage.prices import load_prices, model_price

    topics = resolve_topics(args.topic)
    rate = (model_price("jev-", "interactive", load_prices()) or {}).get("input_usd_per_1m")
    if not rate:
        raise SystemExit("No sourced Jev price in llm/usage/prices.yaml: refusing to run without a cost bound")
    url = _database_url(args.database_url)
    conn = psycopg2.connect(url)
    try:
        if not args.dry_run:
            with conn.cursor() as cur:
                cur.execute(CREATE_SQL)
            conn.commit()
        patterns = topic_patterns(conn, topics)
        done = _done_keys(conn)
        speakers = load_speakers(conn)
        with conn.cursor() as cur:
            cur.execute(MEETING_HEAT_SQL)
            heat_rows = cur.fetchall()
            cur.execute(CONTESTED_SQL)
            contested = {(v, int(t)) for v, t in cur.fetchall()}
        conn.commit()
    finally:
        conn.close()
    heat = meeting_heat_scores(heat_rows, contested, [t.topic_id for t in topics])
    jobs, stats = build_jobs(speakers, topics, patterns, done, year=args.year, heat=heat)
    if args.limit:
        jobs = jobs[: args.limit]
    for slug, st in stats.items():
        st["est_usd_todo"] = round(estimate_usd(st["todo_chars"], st["todo"], rate), 4)
    total_est = estimate_usd(sum(len(j.state) for j in jobs), len(jobs), rate)
    order = [t.slug for t in ordered_topics(topics)]
    for slug in order:
        st = stats[slug]
        logger.info("{:<28} matched {:>6,}  done {:>6,}  to read {:>6,}  ~${:.3f}", slug, st["matched"], st["done"],
                    st["todo"], st["est_usd_todo"])
    logger.info("Total to read: {:,} speaker-topics, about ${:.2f} at ${}/1M input tokens", len(jobs), total_est, rate)
    summary: dict[str, Any] = {"topics": stats, "order": order, "estimated_usd": round(total_est, 4),
                               "read": 0, "failed": 0, "input_tokens": 0, "stopped": None}
    if args.dry_run:
        return summary

    cap = float(args.max_usd)
    conn = psycopg2.connect(url)
    spent = 0.0
    try:
        with JevClient(model=args.model or None) as client, ThreadPoolExecutor(max_workers=args.workers) as pool:
            batch = max(args.workers * 4, 1)
            for start in range(0, len(jobs), batch):
                if spent >= cap:
                    summary["stopped"] = f"budget: ${spent:.4f} reached --max-usd {cap}"
                    break
                chunk = jobs[start: start + batch]
                futures = [
                    pool.submit(ask, client, speaker_id=j.meeting_speaker_id, video_id=j.video_id, topic=j.topic,
                                state=j.state)
                    for j in chunk
                ]
                stop: JevError | None = None
                for j, fut in zip(chunk, futures):
                    try:
                        reading = fut.result()
                    except JevError as exc:
                        if exc.status_code in STOP_STATUSES:
                            stop = exc
                            continue
                        summary["failed"] += 1
                        logger.warning("{} {}: {}", j.topic.slug, j.meeting_speaker_id, exc)
                        continue
                    except Exception as exc:  # noqa: BLE001 - one bad answer never stops the run; it is retried next run
                        summary["failed"] += 1
                        logger.warning("{} {}: {!r}", j.topic.slug, j.meeting_speaker_id, exc)
                        continue
                    with conn.cursor() as cur:
                        cur.execute(UPSERT_SQL, reading.row())
                    conn.commit()
                    summary["read"] += 1
                    stats[j.topic.slug]["read_now"] = stats[j.topic.slug].get("read_now", 0) + 1
                    summary["input_tokens"] += reading.input_tokens or 0
                    spent = summary["input_tokens"] * rate / 1_000_000
                if stop is not None:
                    summary["stopped"] = f"Jev {stop.status_code}: {stop}"
                    logger.error("Stopping cleanly: {} (rerun the same command after a top-up)", stop)
                    break
                if start // batch % 25 == 0:
                    logger.info("{:,}/{:,} read, {:,} input tokens, ${:.4f}", summary["read"], len(jobs),
                                summary["input_tokens"], spent)
    finally:
        conn.close()
    summary["spent_usd"] = round(spent, 4)
    for slug, st in stats.items():
        st["remaining"] = st["todo"] - st.get("read_now", 0)
    summary["remaining_est_usd"] = round(sum(
        estimate_usd(st["todo_chars"] * st["remaining"] // max(st["todo"], 1), st["remaining"], rate)
        for st in stats.values()), 4)
    logger.success("Read {:,} speaker-topics, {:,} failed, {:,} input tokens (${:.4f}); stopped: {}", summary["read"],
                   summary["failed"], summary["input_tokens"], spent, summary["stopped"])
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--topic", default="all", help="all, a slug, or slugs separated by commas")
    p.add_argument("--dry-run", action="store_true", help="count and estimate; send nothing")
    p.add_argument("--max-usd", type=float, default=1.0, help="stop once this run's Jev spend reaches it")
    p.add_argument("--year", type=int, default=2026, help="each topic's speakers from this year on go first")
    p.add_argument("--limit", type=int, default=0, help="read at most this many speaker-topics (0 = all)")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--model", default="")
    p.add_argument("--database-url", default="")
    p.add_argument("--summary-json", default="", help="write the run summary here")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    if args.summary_json:
        from pathlib import Path

        Path(args.summary_json).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return 3 if summary.get("stopped", "") and str(summary["stopped"]).startswith("Jev 40") else 0


if __name__ == "__main__":
    sys.exit(main())
