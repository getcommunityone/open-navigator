"""Split meeting captions into individual public comments, once per meeting (#1233, epic #1232).

    python -m ingestion.meetings.comment_segments                          # every topic meeting, all years
    python -m ingestion.meetings.comment_segments --year 2026              # only 2026 meetings
    python -m ingestion.meetings.comment_segments --year 2026 --dry-run    # segment, print counts, don't write
    python -m ingestion.meetings.comment_segments --video-id 6_vdRi8JqOc --dry-run --show 5
    python -m ingestion.meetings.comment_segments --dsn URL                # write somewhere else

Segmentation is topic-agnostic: a meeting is split into comments ONCE, and every topic reads the
same comments (owner decision, 2026-11-26: "do it once per meeting and not every topic"). The
meetings segmented are those linked to a curated topic (``public.topic_transcript_link``) plus
the data-center set (``public.data_center_meeting_mention``). Their timed caption cues are read
from ``bronze.bronze_event_youtube_transcript`` and one row per detected comment lands in
``bronze.bronze_meeting_comment_segment``. Which topic(s) a comment discusses is decided in dbt
(``meeting_comment``) from the curated topic keywords.

A comment starts at a speaker boundary and runs until the next one. Boundaries, all plain
text rules over the captions (no LLM, no paid call):

  self_intro   a self-introduction: "My name is ...", "my name's ...", "I'm <Name> and I live ...";
  chair_call   the chair calling a speaker: "next speaker", "next is Ms. Cooper", "please come forward",
               "state your name", "you have three minutes";
  turn_marker  the caption tool's ">>" speaker-change marker, used to place the start of a comment
               just before its introduction;
  closing      the chair or timer ending it: "your time is up", "wrap it up", "thank you for your
               comments", "next speaker", "anyone else wish to speak", "close the public hearing";
  pause        a silence of ``PAUSE_SECONDS`` or more between cues;
  max_length   a comment longer than ``MAX_COMMENT_SECONDS`` is cut there.

Only stretches anchored by a self-introduction or a chair call become comments; council
discussion and staff reports without one are not comments. Which comments are public (not staff
or the applicant) and which topics they discuss is decided in dbt (``meeting_comment``,
``data_center_comment``) from seeds, so the keyword rules live in SQL with the rest of the pipeline.

Privacy: ``intro_name`` is the name as the caption heard it and stays in bronze. dbt serves only a
"First L." display form, and none for a possible minor (AGENTS.md, Privacy and data ethics).
Nothing here looks a person up anywhere else. Writes go to the local warehouse; Neon is never read
or written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

SEGMENTER_VERSION = "1.2.0"  # 1.1: home addresses scrubbed; 1.2: wider scrub (we/my house on, lowercase)
TABLE = "bronze.bronze_meeting_comment_segment"

PAUSE_SECONDS = 20.0  # a silence this long ends a comment
START_PAUSE_SECONDS = 3.5  # a silence this long before an intro marks where the speaker started
MAX_COMMENT_SECONDS = 480.0  # no public comment runs longer than 8 minutes; cut there
MAX_BACKOFF_SECONDS = 60.0  # a comment starts at most this long before its introduction
MIN_WORDS = 30  # shorter stretches are procedure, not a comment
BLOCK_GAP_SECONDS = 180.0  # comments closer than this belong to one comment period
INTRO_WORDS = 40  # intro_text keeps this many words from the introduction on

# Self-introductions. Each pattern's group "name" is the name as heard (may be absent).
_NAME = r"(?P<name>(?:(?:dr|mr|mrs|ms|miss)\.?\s+)?[A-Za-z][A-Za-z'\-]+(?:\s+[A-Za-z][A-Za-z'\-]+){0,2})"
INTRO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bmy\s+name\s+is\s+" + _NAME, re.I),
    re.compile(r"\bmy\s+name'?s\s+" + _NAME, re.I),
    re.compile(r"\bname\s+(?:and|&)\s+address\s+(?:is|are)\s+" + _NAME, re.I),
    re.compile(
        r"\b(?:i\s+am|i'm)\s+(?P<name>[A-Z][a-z'\-]+\s+[A-Z][a-z'\-]+)[,.]?\s+(?:and\s+)?i\s+(?:live|reside|own)\b"
    ),
)
# Words that end a heard name ("My name is Lilly and I'm ...").
_NAME_STOP = {
    "and", "i", "im", "i'm", "a", "an", "the", "from", "with", "of", "at", "in", "on", "for", "here", "my", "is",
    "uh", "um", "not", "resident", "live", "who", "but", "so", "to", "we", "it", "this", "that", "good", "evening",
    "hello", "hi", "thank", "you", "again", "just", "as", "also", "been", "was", "am", "lifelong", "born",
}
_HONORIFIC = {"dr", "mr", "mrs", "ms", "miss"}

CHAIR_CALL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnext\s+(?:speaker|up|person|card|commenter|caller)\b", re.I),
    re.compile(r"\b(?:next|first|then)\s+(?:is|we\s+have)\s+(?:mr|mrs|ms|miss|dr)\.?\s+[A-Z]", re.I),
    re.compile(r"\b(?:please\s+)?come\s+(?:forward|on\s+up|up\s+to\s+the\s+(?:podium|mic|microphone))\b", re.I),
    re.compile(r"\bstate\s+your\s+(?:full\s+)?name\b", re.I),
    re.compile(r"\byou\s+(?:have|'ll\s+have|will\s+have)\s+(?:\w+\s+)?(?:three|four|five|two|3|4|5|2)\s+minutes\b", re.I),
)

CLOSING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:your|the)\s+time\s+(?:is\s+up|has\s+expired|has\s+run\s+out)\b", re.I),
    re.compile(r"\btime'?s\s+up\b", re.I),
    re.compile(r"\bwrap\s+(?:it\s+)?up\b", re.I),
    re.compile(r"\bthank\s+you\s+for\s+your\s+(?:comments?|time\s+and\s+comments?|remarks)\b", re.I),
    re.compile(r"\bnext\s+(?:speaker|up|person|card|commenter|caller)\b", re.I),
    re.compile(r"\b(?:is\s+there\s+)?any\s*one\s+else\s+(?:who\s+)?(?:wish(?:es)?|wants?|would\s+like)\s+to\s+(?:speak|address)\b", re.I),
    re.compile(r"\bclose\s+(?:the\s+)?public\s+(?:hearing|comment)\b", re.I),
    re.compile(r"\bpublic\s+(?:hearing|comment)\s+(?:is|are)\s+(?:now\s+)?closed\b", re.I),
)

SECTION_OPEN = re.compile(
    r"\b(?:open(?:ing)?\s+(?:the\s+)?public\s+(?:hearing|comment)|public\s+comment\s+(?:period|portion|section)"
    r"|citizens?\s+(?:to\s+be\s+heard|comments?|participation)|public\s+participation|audience\s+comments?"
    r"|comments?\s+from\s+the\s+public|public\s+(?:hearing|comment)s?\s+(?:is|are)\s+(?:now\s+)?open)\b",
    re.I,
)
SECTION_CLOSE = re.compile(
    r"\b(?:close\s+(?:the\s+)?public\s+(?:hearing|comment)|public\s+(?:hearing|comment)\s+(?:is|are)\s+(?:now\s+)?closed"
    r"|(?:that\s+)?conclud(?:es|ing)\s+(?:the\s+)?public\s+(?:hearing|comment))\b",
    re.I,
)

# --- Personal location scrub (AGENTS.md, Privacy and data ethics) ------------------------------
# A resident's own home address or street is never stored. Two rules, applied before any text lands:
#   1. what follows "I live at / my address is / I reside at / I live on|off" up to the next pause
#      in punctuation (at most 8 words) becomes "[address removed]" ("I live in Joliet", a town, stays);
#   2. any house-number street address ("1703 Heritage Point", "412 N. Oak Street") is replaced too.
# Public places (Route 9, Greene County, a project site) are kept: they have no house number.
ADDRESS_REDACTION = "[address removed]"
_STREET_SUFFIX = (
    r"(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|way|boulevard|blvd|circle|cir|place|pl|trail|trl"
    r"|point|pointe|terrace|ter|parkway|pkwy|highway|hwy|pike|run|loop|crossing|ridge|hollow|cove|square|sq)"
)
# "I live on / we live right on / my house is on / my address is ..." — the words after it are the home location.
_LIVE_AT = re.compile(
    r"\b(?:(?:i|we)(?:'ve|\s+have)?\s+(?:(?:right|just|down|out|up)\s+)?(?:live|lived|reside|resided)"
    r"|(?:my|our)\s+(?:home|house|farm|property|place|residence)\s+(?:is\s+)?"
    r"|(?:my|our)\s+(?:home\s+|street\s+|mailing\s+)?address\s+is"
    r"|i(?:'m|\s+am)\s+located)"
    r"\s*(?:(?:right|just)\s+)?(?:at|on|off\s+of|off|along)?\s*",
    re.I,
)
# Where the home location ends: punctuation, or a word that starts the next clause.
_LOCATION_END = re.compile(
    r"[.,;!?]|\b(?:and|in|which|for|since|so|i|been|where|near|about|is|was|we|my|but|because|across|next|with"
    r"|who|that|from|to|it|they|our|the\s+site|this|there|here)\b",
    re.I,
)
_MAX_LOCATION_WORDS = 5
# Words that make "<number> <words> road" a measurement, not a house address ("300 acres on Ridge Road").
_NOT_STREET_WORD = (
    r"(?!(?:acres?|feet|foot|miles?|megawatts?|mw|gallons?|on|of|the|from|to|at|and|in|near|off|along|by|units?"
    r"|homes?|houses?|people|jobs|years?|percent|minutes?|trucks?|lanes?)\b)"
)
_HOUSE_ADDRESS = re.compile(
    r"\b\d{1,6}(?:-\d{1,4})?\s+(?:(?:[NSEW]\.?|north|south|east|west)\s+)?"
    r"(?:" + _NOT_STREET_WORD + r"[A-Za-z][A-Za-z'\-]*\s+){1,4}" + _STREET_SUFFIX + r"\b\.?",
    re.I,
)


def _scrub_live_at(text: str) -> str:
    out: list[str] = []
    pos = 0
    for m in _LIVE_AT.finditer(text):
        if m.start() < pos:
            continue
        rest = text[m.end() :]
        # "I live in Joliet" names a town: only a street-level preposition (or an address phrase) is scrubbed.
        phrase = m.group(0).lower()
        has_prep = re.search(r"\b(at|on|off|along)\s*$", phrase) is not None
        # "my home is 12 Elm Street" (a number follows) or "my address is ..." scrub; "my home is very
        # important" and "our property values" don't.
        if not has_prep and "address" not in phrase and not re.match(r"\s*\d", rest):
            continue
        if re.match(r"\s*(in|near|by|around|outside|within|close)\b", rest, re.I) and not re.search(
            r"\b(at|on|off|along)\s*$", phrase
        ):
            continue
        stop = _LOCATION_END.search(rest)
        cut = stop.start() if stop else len(rest)
        words = re.finditer(r"\S+", rest[:cut])
        spans = [w.end() for w in words]
        if not spans:
            continue
        end = spans[min(len(spans), _MAX_LOCATION_WORDS) - 1]
        out.append(text[pos : m.end()] + ADDRESS_REDACTION)
        pos = m.end() + end
    out.append(text[pos:])
    return "".join(out)


def scrub_personal_location(text: str | None) -> str | None:
    """Text with a speaker's home address / street of residence replaced by ``ADDRESS_REDACTION``."""
    if not text:
        return text
    out = _scrub_live_at(text)
    out = _HOUSE_ADDRESS.sub(ADDRESS_REDACTION, out)
    return out


# Caption-tool notes that aren't speech.
_NOTE = re.compile(r"\[\d+ SECONDS? PAUSE\]|<\d+ MINUTES? PASSED>|\[(?:music|applause|laughter|inaudible|snorts?)\]", re.I)
TURN_MARKER = ">>"


@dataclass(frozen=True)
class Cue:
    """One timed caption cue."""

    start: float
    duration: float
    text: str

    @property
    def end(self) -> float:
        return self.start + max(self.duration, 0.0)


@dataclass(slots=True)
class Token:
    """One word of the caption stream with the time it was (approximately) said."""

    text: str
    t: float
    char_start: int  # offset in the joined text
    turn_break: bool = False  # a ">>" came right before this word
    pause_before: float = 0.0  # silence between the previous cue's end and this cue's start


@dataclass
class Comment:
    """One detected comment (a bronze row before keys)."""

    video_id: str
    comment_index: int
    block_index: int
    start_seconds: float
    end_seconds: float
    comment_text: str
    word_count: int
    intro_text: str | None
    intro_name: str | None
    boundary_basis: str  # how it started and ended, e.g. "self_intro>closing"
    in_public_comment_section: bool
    segmenter_version: str = SEGMENTER_VERSION
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def comment_segment_id(self) -> str:
        # Start and end together: two comments can share a start second when caption cues carry no duration.
        return hashlib.md5(f"{self.video_id}|{self.start_seconds:.3f}|{self.end_seconds:.3f}".encode()).hexdigest()

    def row(self) -> tuple[Any, ...]:
        return (
            self.comment_segment_id,
            self.video_id,
            self.comment_index,
            self.block_index,
            round(self.start_seconds, 3),
            round(self.end_seconds, 3),
            self.comment_text,
            self.word_count,
            self.intro_text,
            self.intro_name,
            self.boundary_basis,
            self.in_public_comment_section,
            self.segmenter_version,
        )


# --------------------------------------------------------------------------------------------
# Cues -> tokens
# --------------------------------------------------------------------------------------------


def cues_from_segments(segments: Any) -> list[Cue]:
    """Timed cues from the transcript's ``segments`` JSON (list of {text, start, duration})."""
    if isinstance(segments, str):
        try:
            segments = json.loads(segments)
        except ValueError:
            return []
    if not isinstance(segments, list):
        return []
    cues: list[Cue] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        try:
            start = float(seg.get("start"))
        except (TypeError, ValueError):
            continue
        try:
            duration = float(seg.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        text = str(seg.get("text") or "")
        if text.strip():
            cues.append(Cue(start, duration, text))
    cues.sort(key=lambda c: c.start)
    return cues


_TIMED_MARK = re.compile(r"\{(\d+):(\d\d):(\d\d)\}([^{]*)")


def cues_from_timed_text(caption_text_timed: str | None) -> list[Cue]:
    """Cues from ``caption_text_timed`` ("{HH:MM:SS} words ..."); duration runs to the next marker."""
    if not caption_text_timed:
        return []
    marks = [
        (int(h) * 3600 + int(m) * 60 + int(s), body) for h, m, s, body in _TIMED_MARK.findall(caption_text_timed)
    ]
    cues: list[Cue] = []
    for i, (start, body) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else start + 2
        if body.strip():
            cues.append(Cue(float(start), float(max(nxt - start, 0)), body))
    return cues


def tokenize(cues: Sequence[Cue]) -> tuple[list[Token], str]:
    """Words with approximate times (spread evenly over each cue), and the joined text they index."""
    tokens: list[Token] = []
    parts: list[str] = []
    offset = 0
    prev_end: float | None = None
    for cue in cues:
        text = _NOTE.sub(" ", cue.text.replace("\n", " "))
        words = text.split()
        pause = 0.0 if prev_end is None else max(cue.start - prev_end, 0.0)
        # Captions often overlap (duration runs past the next start); measure silence from the next start.
        prev_end = cue.end
        if not words:
            continue
        speech = [w for w in words if w != TURN_MARKER]
        n = max(len(speech), 1)
        k = 0
        pending_break = False
        first = True
        for w in words:
            if w == TURN_MARKER:
                pending_break = True
                continue
            t = cue.start + cue.duration * (k / n) if cue.duration > 0 else cue.start
            tokens.append(Token(w, t, offset, pending_break, pause if first else 0.0))
            parts.append(w)
            offset += len(w) + 1
            pending_break = False
            first = False
            k += 1
    return tokens, " ".join(parts)


def _token_at(tokens: Sequence[Token], char_pos: int) -> int:
    """Index of the token that contains (or starts after) a character offset of the joined text."""
    lo, hi = 0, len(tokens)
    while lo < hi:
        mid = (lo + hi) // 2
        if tokens[mid].char_start <= char_pos:
            lo = mid + 1
        else:
            hi = mid
    return max(lo - 1, 0)


# --------------------------------------------------------------------------------------------
# Anchors and boundaries
# --------------------------------------------------------------------------------------------


def clean_name(raw: str | None) -> str | None:
    """The name as heard, cut at the first word that isn't part of a name; None if nothing name-like is left."""
    if not raw:
        return None
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", raw)
    kept: list[str] = []
    for w in words:
        lw = w.lower().strip("'")
        if lw in _HONORIFIC and not kept:
            continue
        if lw in _NAME_STOP:
            break
        kept.append(w)
        if len(kept) == 3:
            break
    if not kept or len(kept[0]) < 2:
        return None
    return " ".join(k[:1].upper() + k[1:].lower() if k.isupper() or k.islower() else k for k in kept)


@dataclass(frozen=True)
class Anchor:
    token_index: int
    kind: str  # self_intro | chair_call
    name: str | None


def find_anchors(tokens: Sequence[Token], text: str) -> list[Anchor]:
    """Self-introductions and chair calls, in order; a chair call followed by an intro within 45 s is one anchor."""
    raw: list[Anchor] = []
    for pat in INTRO_PATTERNS:
        for m in pat.finditer(text):
            raw.append(Anchor(_token_at(tokens, m.start()), "self_intro", clean_name(m.groupdict().get("name"))))
    for pat in CHAIR_CALL_PATTERNS:
        for m in pat.finditer(text):
            # The comment starts after the call, at the next word.
            idx = min(_token_at(tokens, m.end()) + 1, len(tokens) - 1)
            raw.append(Anchor(idx, "chair_call", None))
    raw.sort(key=lambda a: (a.token_index, a.kind != "self_intro"))

    merged: list[Anchor] = []
    for a in raw:
        if merged:
            last = merged[-1]
            dt = tokens[a.token_index].t - tokens[last.token_index].t
            if dt < 45.0:
                if last.kind == "chair_call" and a.kind == "self_intro":
                    # The call opens the comment; the intro names the speaker.
                    merged[-1] = Anchor(last.token_index, "chair_call+self_intro", a.name)
                    continue
                if last.kind.endswith("self_intro") and a.kind == "self_intro" and dt < 20.0:
                    continue  # "my name is ... my name is" restated
                if a.kind == "chair_call" and last.kind.startswith("chair_call"):
                    continue  # one call phrased twice
        merged.append(a)
    return merged


def _matches_in(patterns: Iterable[re.Pattern[str]], text: str) -> list[int]:
    return sorted(m.start() for p in patterns for m in p.finditer(text))


def _section_flags(tokens: Sequence[Token], text: str) -> list[bool]:
    """Per token: is it inside an opened (and not yet closed) public comment/hearing section."""
    events = [(_token_at(tokens, m.start()), 1) for m in SECTION_OPEN.finditer(text)]
    events += [(_token_at(tokens, m.start()), 0) for m in SECTION_CLOSE.finditer(text)]
    events.sort()
    flags = [False] * len(tokens)
    state = False
    j = 0
    for i in range(len(tokens)):
        while j < len(events) and events[j][0] <= i:
            state = bool(events[j][1])
            j += 1
        flags[i] = state
    return flags


def _start_index(tokens: Sequence[Token], anchor: Anchor, floor_index: int) -> int:
    """Back up from a self-introduction to where the speaker began ("Good evening, Mayor... my name is")."""
    i = anchor.token_index
    if anchor.kind.startswith("chair_call"):
        return max(i, floor_index)
    t0 = tokens[i].t
    j = i
    while j > floor_index:
        tok = tokens[j]
        if tok.turn_break or tok.pause_before >= START_PAUSE_SECONDS:
            return j
        if t0 - tokens[j - 1].t > MAX_BACKOFF_SECONDS:
            break
        j -= 1
    # No marker: start at the sentence that holds the intro, at most 12 words back.
    k = i
    while k > max(floor_index, i - 12):
        if re.search(r"[.?!]$", tokens[k - 1].text):
            break
        k -= 1
    return k


def _end_index(tokens: Sequence[Token], start: int, limit: int, closing_tokens: set[int]) -> tuple[int, str]:
    """Last token (exclusive) of a comment that starts at ``start`` and may run to ``limit``."""
    t_start = tokens[start].t
    words = 0
    for j in range(start + 1, limit):
        words += 1
        tok = tokens[j]
        if tok.pause_before >= PAUSE_SECONDS and words >= MIN_WORDS:
            return j, "pause"
        if j in closing_tokens and words >= MIN_WORDS:
            return j, "closing"
        if tok.t - t_start > MAX_COMMENT_SECONDS:
            return j, "max_length"
    return limit, "next_speaker"


def segment_comments(video_id: str, cues: Sequence[Cue]) -> list[Comment]:
    """All comments detected in one meeting's cues, in time order."""
    tokens, text = tokenize(cues)
    if not tokens:
        return []
    anchors = find_anchors(tokens, text)
    if not anchors:
        return []
    closing_tokens = {_token_at(tokens, pos) for pos in _matches_in(CLOSING_PATTERNS, text)}
    section = _section_flags(tokens, text)

    comments: list[Comment] = []
    floor = 0
    for n, anchor in enumerate(anchors):
        if anchor.token_index < floor:
            continue
        start = _start_index(tokens, anchor, floor)
        nxt = anchors[n + 1] if n + 1 < len(anchors) else None
        limit = len(tokens)
        if nxt is not None:
            limit = max(_start_index(tokens, nxt, anchor.token_index + 1), anchor.token_index + 1)
        end, end_basis = _end_index(tokens, start, limit, closing_tokens)
        floor = end
        span = tokens[start:end]
        if len(span) < MIN_WORDS:
            continue
        intro_at = anchor.token_index if anchor.kind.endswith("self_intro") else start
        intro_tokens = tokens[intro_at : min(intro_at + INTRO_WORDS, end)]
        last = span[-1]
        comments.append(
            Comment(
                video_id=video_id,
                comment_index=0,
                block_index=0,
                start_seconds=span[0].t,
                end_seconds=max(last.t, span[0].t),
                comment_text=scrub_personal_location(" ".join(t.text for t in span)) or "",
                word_count=len(span),
                intro_text=scrub_personal_location(" ".join(t.text for t in intro_tokens)) or None,
                intro_name=anchor.name,
                boundary_basis=f"{anchor.kind}>{end_basis}",
                in_public_comment_section=section[start],
            )
        )

    # Identical spans (cues with no duration) are one comment.
    seen: set[tuple[float, float]] = set()
    unique: list[Comment] = []
    for c in comments:
        key = (round(c.start_seconds, 3), round(c.end_seconds, 3))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    comments = unique

    block = 0
    for i, c in enumerate(comments):
        if i and c.start_seconds - comments[i - 1].end_seconds > BLOCK_GAP_SECONDS:
            block += 1
        c.comment_index = i
        c.block_index = block
    return comments


# --------------------------------------------------------------------------------------------
# Warehouse I/O
# --------------------------------------------------------------------------------------------

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    comment_segment_id        text PRIMARY KEY,
    video_id                  text NOT NULL,
    comment_index             integer NOT NULL,
    block_index               integer NOT NULL,
    start_seconds             numeric(12, 3) NOT NULL,
    end_seconds               numeric(12, 3) NOT NULL,
    comment_text              text NOT NULL,
    word_count                integer NOT NULL,
    intro_text                text,
    intro_name                text,
    boundary_basis            text NOT NULL,
    in_public_comment_section boolean NOT NULL,
    segmenter_version         text NOT NULL,
    loaded_at                 timestamp NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bronze_meeting_comment_segment_video_idx ON {TABLE} (video_id);
"""

INSERT_SQL = f"""
INSERT INTO {TABLE} (
    comment_segment_id, video_id, comment_index, block_index, start_seconds, end_seconds, comment_text,
    word_count, intro_text, intro_name, boundary_basis, in_public_comment_section, segmenter_version
) VALUES %s
ON CONFLICT (comment_segment_id) DO UPDATE SET
    comment_index = excluded.comment_index, block_index = excluded.block_index,
    end_seconds = excluded.end_seconds, comment_text = excluded.comment_text,
    word_count = excluded.word_count, intro_text = excluded.intro_text, intro_name = excluded.intro_name,
    boundary_basis = excluded.boundary_basis, in_public_comment_section = excluded.in_public_comment_section,
    segmenter_version = excluded.segmenter_version, loaded_at = now()
"""

# Meetings to segment: every meeting a curated topic links to, plus the data-center set.
VIDEOS_SQL = """
    select video_id from (
        select trim(video_id) as video_id, event_date as meeting_date from public.topic_transcript_link
        union
        select trim(video_id), meeting_date from public.data_center_meeting_mention
    ) as m
    where video_id is not null and video_id <> ''
      and (%(all_years)s or extract(year from meeting_date)::int = %(year)s)
    group by video_id
    order by video_id
"""

TRANSCRIPT_SQL = """
    select trim(video_id), segments, caption_text_timed
    from bronze.bronze_event_youtube_transcript
    where trim(video_id) = any(%(ids)s)
      and lower(coalesce(trim(transcript_source), '')) not like 'excluded:%%'
      and lower(coalesce(trim(transcript_source), '')) not like 'tombstone:%%'
"""


def _dsn(explicit: str | None = None) -> str:
    """``--dsn``, else ``OPEN_NAVIGATOR_DATABASE_URL`` / ``DATABASE_URL`` (Postgres). Neon is refused."""
    for candidate in (explicit, os.environ.get("OPEN_NAVIGATOR_DATABASE_URL"), os.environ.get("DATABASE_URL")):
        url = (candidate or "").strip()
        if url.startswith(("postgresql:", "postgres:")):
            if "neon.tech" in url:
                raise SystemExit("Refusing to write comment segments to Neon; use the local warehouse.")
            return url
    raise SystemExit("Set OPEN_NAVIGATOR_DATABASE_URL (the local warehouse) or pass --dsn.")


def load_cues(cur: Any, video_ids: Sequence[str]) -> dict[str, list[Cue]]:
    cur.execute(TRANSCRIPT_SQL, {"ids": list(video_ids)})
    out: dict[str, list[Cue]] = {}
    for vid, segments, timed in cur.fetchall():
        cues = cues_from_segments(segments) or cues_from_timed_text(timed)
        if cues and len(cues) > len(out.get(vid, [])):
            out[vid] = cues
    return out


def _segment_one(item: tuple[str, list[Cue]]) -> tuple[str, list[tuple[Any, ...]], list[str]]:
    """Worker: one meeting's rows, plus a few log lines for --show."""
    vid, cues = item
    comments = segment_comments(vid, cues)
    lines = [
        f"{vid} {c.start_seconds:.0f}-{c.end_seconds:.0f}s {c.word_count} words [{c.boundary_basis}] intro={c.intro_text!r}"
        for c in comments
    ]
    return vid, [c.row() for c in comments], lines


def run(
    *,
    year: int | None,
    all_years: bool,
    video_ids: Sequence[str] | None,
    dsn: str,
    dry_run: bool,
    show: int = 0,
    batch: int = 200,
    workers: int = 1,
) -> dict[str, int]:
    from concurrent.futures import ProcessPoolExecutor

    import psycopg2
    from psycopg2.extras import execute_values

    stats = {"meetings": 0, "meetings_untimed": 0, "meetings_with_comments": 0, "comments": 0}
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        if video_ids:
            ids = list(dict.fromkeys(video_ids))
        else:
            cur.execute(VIDEOS_SQL, {"all_years": all_years, "year": year or 0})
            ids = [r[0] for r in cur.fetchall()]
        stats["meetings"] = len(ids)
        logger.info("Segmenting comments in {:,} meetings", len(ids))
        if not dry_run:
            cur.execute(DDL)
        shown = 0
        pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
        for i in range(0, len(ids), batch):
            chunk = ids[i : i + batch]
            cues_by_video = load_cues(cur, chunk)
            stats["meetings_untimed"] += sum(1 for vid in chunk if vid not in cues_by_video)
            items = [(vid, cues_by_video[vid]) for vid in chunk if vid in cues_by_video]
            results = pool.map(_segment_one, items, chunksize=4) if pool else map(_segment_one, items)
            rows: list[tuple[Any, ...]] = []
            for _vid, vid_rows, lines in results:
                if vid_rows:
                    stats["meetings_with_comments"] += 1
                stats["comments"] += len(vid_rows)
                rows.extend(vid_rows)
                for line in lines:
                    if shown < show:
                        shown += 1
                        logger.info(line)
            if not dry_run:
                # Re-segmenting a meeting replaces its rows, so a changed boundary leaves no stale comment.
                cur.execute(f"DELETE FROM {TABLE} WHERE video_id = any(%s)", (list(chunk),))
                if rows:
                    execute_values(cur, INSERT_SQL, rows, page_size=500)
                conn.commit()
            logger.info("{:,}/{:,} meetings, {:,} comments so far", min(i + batch, len(ids)), len(ids), stats["comments"])
        if pool:
            pool.shutdown()
    logger.success(
        "{:,} comments in {:,} of {:,} meetings ({:,} without timed captions){}",
        stats["comments"], stats["meetings_with_comments"], stats["meetings"], stats["meetings_untimed"],
        " [dry run, nothing written]" if dry_run else f" -> {TABLE}",
    )
    return stats


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--year", type=int, help="only meetings in this year (default: all years)")
    scope.add_argument("--video-id", action="append", help="segment only these meetings (repeatable)")
    parser.add_argument("--dsn", help="Postgres URL (default: OPEN_NAVIGATOR_DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", help="segment and report; write nothing")
    parser.add_argument("--show", type=int, default=0, help="log the first N comments found")
    parser.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 2, 1), help="segmenting processes")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover - dotenv is optional
        pass
    run(
        year=args.year,
        all_years=args.year is None and not args.video_id,
        video_ids=args.video_id,
        dsn=_dsn(args.dsn),
        dry_run=args.dry_run,
        show=args.show,
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
