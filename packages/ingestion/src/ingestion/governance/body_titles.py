"""Meeting title -> governing body (#1442).

A meeting's title or body field names the body that met, in many spellings: "Tuscaloosa Zoning Board of
Adjustments", "Zoning Board of Adjustment Meeting - Oct 26, 2026", "BOC Business Session". This module is the
Python mirror of the dbt macro ``clean_meeting_title_for_body`` plus the ordered pattern seed
``dbt_project/seeds/governing_body_pattern.csv``. The warehouse does the real work in dbt
(``int_meeting_body__matched``); this mirror exists so pytest can pin the behaviour on real titles, and a dbt
singular test (``assert_governing_body_title_examples``) checks the SQL gives the same answers on the same example
seed (``governing_body_title_example.csv``). Change both together.

Steps, identical in SQL:

1. ``clean_title``: lower-case; drop bracketed text, dates, times and years; turn every character outside
   ``[a-z0-9&]`` into a space; drop the jurisdiction's own name at the start ("city of tuscaloosa", "tuscaloosa");
   drop filler words ("meeting", "regular", "livestream", ...); collapse spaces.
2. Try the seed patterns in priority order, keeping only rows whose ``applies_to`` fits the jurisdiction type.
   The first match wins. ``__skip__`` means "a body that isn't this jurisdiction's" (a county commission in a
   city's video): no body. ``__generic__`` builds the key from the cleaned name ("finance committee" ->
   ``committee:finance_committee``).

Patterns use only regex syntax that Postgres (ARE, ``~*``) and Python ``re`` read the same way: no ``\\b``, word
edges written as ``(^| )`` and ``( |$)`` over the single-spaced cleaned text.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

# --------------------------------------------------------------------------------------------------------------------
# Cleaning (mirrors dbt_project/macros/clean_meeting_title_for_body.sql; keep the regexes byte-identical)
# --------------------------------------------------------------------------------------------------------------------

MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
WEEKDAYS = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)"

# Each (pattern, replacement) runs in order with global replacement on the lower-cased title.
CLEAN_STEPS: tuple[tuple[str, str], ...] = (
    (r"[\(\[][^\)\]]*[\)\]]", " "),
    (MONTHS + r" [0-9]{1,2}(st|nd|rd|th)?,? [0-9]{4}", " "),
    (r"[0-9]{1,2}(st|nd|rd|th)? " + MONTHS + r",? [0-9]{4}", " "),
    (MONTHS + r" [0-9]{1,2}(st|nd|rd|th)?", " "),
    (MONTHS + r",? [0-9]{4}", " "),
    (r"[0-9]{4}[/.-][0-9]{1,2}[/.-][0-9]{1,2}", " "),
    (r"[0-9]{1,2}[/.-][0-9]{1,2}[/.-][0-9]{2,4}", " "),
    (r"[0-9]{1,2}[/.-][0-9]{1,2}", " "),
    (r"[0-9]{1,2}(:[0-9]{2})? ?(am|pm|a\.m\.|p\.m\.)", " "),
    (r"(19|20)[0-9]{2}", " "),
    (r"['’]s( |$)", " "),
    (r"['’]", ""),
    (r"[^a-z0-9&]+", " "),
    (r"(^| )" + WEEKDAYS + r"( |$)", " "),
)

# Filler words dropped after the jurisdiction name is removed. Multi-word alternatives come before any alternative
# that is their prefix, so Postgres (leftmost-longest) and Python (leftmost-first) remove the same text.
FILLER = (
    r"(^| )(regular session|special session|business session|voting session|executive session|closed session"
    r"|public hearing|live stream|no audio|in person|of the city|of the town|part [0-9]+|pt [0-9]+|day [0-9]+"
    r"|livestreamed|livestream|streaming|stream|live|meetings|meeting|mtg|regular|special|called"
    r"|recessed|adjourned|reconvened|continued|emergency|rescheduled|scheduled|agenda|minutes|video|recording"
    r"|replay|official|monthly|quarterly|annual|joint|hearing|edited|full|archived|archive|audio|zoom|virtual"
    r"|hybrid)(?= |$)"
)

# A state name or USPS code right after the place name ("Nashville NC, Council Meeting") is not part of the body.
# Multi-word names first (Postgres picks the longest alternative, Python the first).
STATE_PREFIX = (
    r"^(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|al|ak|az|ar|ca|co|ct|de|dc|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)( |$)"
)

_SPACES = re.compile(r" +")


def _base_name(jurisdiction_name: Optional[str]) -> str:
    """The jurisdiction's name without its kind ("Tuscaloosa County" -> "tuscaloosa")."""
    name = re.sub(r"[^a-z0-9&]+", " ", (jurisdiction_name or "").lower()).strip()
    name = re.sub(r"( city| county)?( school district| schools)$", "", name)
    name = re.sub(r" (county|parish|borough|city|town|village|township|cdp|ccd|municipality)$", "", name)
    return name.strip()


def clean_title(title: Optional[str], jurisdiction_name: Optional[str] = None) -> str:
    """The title reduced to the words that can name a body (lower-case, single-spaced)."""
    t = (title or "").lower()
    for pattern, repl in CLEAN_STEPS:
        t = re.sub(pattern, repl, t)
    t = _SPACES.sub(" ", t).strip()
    t = re.sub(r"^(the )?((city|town|village|borough|township|county|parish) of )", "", t)
    base = _base_name(jurisdiction_name)
    if base and (t == base or t.startswith(base + " ")):
        t = t[len(base):].strip()
    if " " in t:
        t = re.sub(STATE_PREFIX, "", t)
    t = re.sub(FILLER, " ", t)
    t = _SPACES.sub(" ", t).strip()
    t = re.sub(r"^(the|and|of|for|at|on) ", "", t)
    t = re.sub(r" (and|of|for|at|on|the)$", "", t)
    return t.strip()


# --------------------------------------------------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BodyPattern:
    pattern_id: str
    priority: int
    applies_to: str
    pattern: str
    body_key: str
    body_name: str
    body_type: str
    name_from_title: bool

    @property
    def regex(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


@dataclass(frozen=True)
class BodyMatch:
    body_key: str
    body_name: Optional[str]
    body_type: str
    pattern_id: str
    cleaned: str


def default_seed_path(filename: str = "governing_body_pattern.csv") -> Path:
    """The dbt seed, found by walking up from this file to the repository's ``dbt_project/seeds``."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "dbt_project" / "seeds" / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"dbt_project/seeds/{filename} not found above {here}")


def load_patterns(path: Optional[Path] = None) -> list[BodyPattern]:
    with open(path or default_seed_path(), newline="", encoding="utf-8") as fh:
        rows = [
            BodyPattern(
                pattern_id=r["pattern_id"],
                priority=int(r["priority"]),
                applies_to=r["applies_to"],
                pattern=r["pattern"],
                body_key=r["body_key"],
                body_name=r["body_name"] or "",
                body_type=r["body_type"] or "",
                name_from_title=(r.get("name_from_title") or "").strip().lower() == "true",
            )
            for r in csv.DictReader(fh)
        ]
    return sorted(rows, key=lambda p: (p.priority, p.pattern_id))


def jurisdiction_kind(jurisdiction_type: Optional[str]) -> str:
    """Seed ``applies_to`` family for a jurisdiction type: county, school_district, state or municipal."""
    jt = (jurisdiction_type or "").lower()
    if jt in ("county", "school_district", "state"):
        return jt
    return "municipal"


def _applies(p: BodyPattern, kind: str) -> bool:
    return p.applies_to == "any" or p.applies_to == kind


_SMALL_WORDS = frozenset({"and", "of", "the", "for", "on", "at", "to", "in"})


def display_name(cleaned: str) -> str:
    """Each word capitalised, small words after the first kept lower-case ("planning and zoning" -> "Planning and
    Zoning"). Word by word, exactly as the SQL does it (``initcap`` would also capitalise after "&")."""
    out = []
    for i, w in enumerate(cleaned.split(" ")):
        out.append(w if (i > 0 and w in _SMALL_WORDS) else w[:1].upper() + w[1:])
    return " ".join(out)


def slug(cleaned: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", cleaned.replace("&", " and ")).strip("_")


def match_body(
    title: Optional[str],
    jurisdiction_name: Optional[str],
    jurisdiction_type: Optional[str],
    patterns: Sequence[BodyPattern],
) -> Optional[BodyMatch]:
    """The body a meeting title names, or None (no body, or a body that isn't this jurisdiction's)."""
    cleaned = clean_title(title, jurisdiction_name)
    if not cleaned:
        return None
    kind = jurisdiction_kind(jurisdiction_type)
    for p in patterns:
        if not _applies(p, kind) or not p.regex.search(cleaned):
            continue
        if p.body_key == "__skip__":
            return None
        if p.body_key == "__generic__":
            return BodyMatch(f"{p.body_type}:{slug(cleaned)}", display_name(cleaned), p.body_type, p.pattern_id, cleaned)
        key, btype = p.body_key, p.body_type
        # A school district's own board is its governing body.
        if kind == "school_district" and key == "governing_body":
            key, btype = "school_board", "school_board"
        # name_from_title: the words the pattern matched ("tuscaloosa city council" -> "City Council"); the patterns
        # that set it are anchored at the end, so Postgres and Python match the same text.
        name = p.body_name or (display_name(p.regex.search(cleaned).group(0).strip()) if p.name_from_title else None)
        return BodyMatch(key, name, btype, p.pattern_id, cleaned)
    return None


def normalize_body(
    title: Optional[str],
    jurisdiction_name: Optional[str] = None,
    jurisdiction_type: Optional[str] = "city",
    patterns: Optional[Iterable[BodyPattern]] = None,
) -> Optional[BodyMatch]:
    """Convenience wrapper that loads the seed when no patterns are given."""
    return match_body(title, jurisdiction_name, jurisdiction_type, list(patterns) if patterns is not None else load_patterns())
