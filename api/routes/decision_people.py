"""
Who supported and opposed a decision, from the speaker slugs the decision record carries (#1320).

``event_decision.competing_views`` names who held each view: ``dominant_view.held_by`` and ``counter_views[].held_by``,
as slugs the meeting analysis wrote, ``<name>_<role>_<place>[_<geoid>]`` ("john_faile_councilor_tuscaloosa",
"chief_sky_unknown_tuscaloosa", "unknown_unknown_unknown_pickens_13227"). This module turns them into people a card can
show, by the privacy rules (AGENTS.md, "Privacy and data ethics"):

- **Officials are public**: a slug whose role is an official title (councilor, mayor, commissioner, chair, chief, ...),
  or whose name matches exactly one current official of the decision's own government (``person_government``, office
  'government', "<jurisdiction> Government", same state), is shown by full name. The role is shown only when it is
  reliable: the official record's title, else the slug's own title word. A title heard only as a form of address
  ("chief_sky_unknown") stays in the name ("Chief Sky") with no role.
- **Everyone else** is "First L." with no role, and only when a first and last name are on record (one word, or an
  honorific and a surname such as "mrs_gonzalez", may be a surname and is left out). Anyone the slug calls a student, minor or child is never shown, and no one but officials
  is shown for a school-board decision.
- A slug with no recoverable name, or with no role and no way to tell the place from the name, is left out. Nothing is
  guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel

Kind = Literal["official", "resident"]


class DecisionPerson(BaseModel):
    """One person on a decision's side (#1320)."""

    name: str
    # The official's title (from person_government, else the slug's title word); None for everyone else.
    role: Optional[str] = None
    kind: Kind


class DecisionPeople(BaseModel):
    """Who was on each side of a decision, and its recorded vote (#1320). Shared by the topic and data-center decisions."""

    supported_by: list[DecisionPerson] = []
    opposed_by: list[DecisionPerson] = []
    # Others the record says spoke on the item (decision_speakers), on no recorded side.
    spoke_on_it: list[DecisionPerson] = []
    # The main view's label as the record words it.
    supported_view: Optional[str] = None
    # False: no counter view on record ("No opposition recorded"); None: the record has no competing views.
    opposition_recorded: Optional[bool] = None
    vote_yes: Optional[int] = None
    vote_no: Optional[int] = None

#: Never shown: the slug says the person is a child or a student (AGENTS.md, minors and students).
MINOR_TOKENS = frozenset({"student", "students", "minor", "child", "children", "kid", "kids", "youth", "teen", "teenager", "juvenile", "pupil"})

#: Form-of-address words that can lead a slug. Honorifics say nothing about office; titles do (but not reliably a role).
HONORIFICS = frozenset({"mr", "mrs", "ms", "miss", "dr", "rev", "reverend", "sir"})
LEAD_TITLES = frozenset(
    {"mayor", "councilmember", "councilman", "councilwoman", "councilor", "commissioner", "chief", "alderman", "alderwoman",
     "chair", "chairman", "chairwoman", "trustee", "supervisor", "sheriff", "judge", "selectman", "selectwoman", "officer",
     "superintendent", "director"}
)

# Role phrases as token tuples -> (label, official). Longest phrases are tried first, so "city attorney" (an official)
# wins over "attorney" (anyone's lawyer) and "council member" over "member".
_ROLE_PHRASES: dict[tuple[str, ...], tuple[Optional[str], bool]] = {
    ("mayor", "pro", "tem"): ("Mayor Pro Tem", True),
    ("mayor", "pro", "tim"): ("Mayor Pro Tem", True),
    ("vice", "mayor"): ("Vice Mayor", True),
    ("deputy", "mayor"): ("Deputy Mayor", True),
    ("mayor",): ("Mayor", True),
    ("city", "council", "member"): ("Council Member", True),
    ("council", "member"): ("Council Member", True),
    ("council", "president"): ("Council President", True),
    ("councilmember",): ("Councilmember", True),
    ("councilman",): ("Councilman", True),
    ("councilwoman",): ("Councilwoman", True),
    ("councilor",): ("Councilor", True),
    ("councillor",): ("Councillor", True),
    ("alderman",): ("Alderman", True),
    ("alderwoman",): ("Alderwoman", True),
    ("alderperson",): ("Alderperson", True),
    ("county", "commissioner"): ("County Commissioner", True),
    ("commissioner",): ("Commissioner", True),
    ("supervisor",): ("Supervisor", True),
    ("selectman",): ("Selectman", True),
    ("selectwoman",): ("Selectwoman", True),
    ("select", "board", "member"): ("Select Board Member", True),
    ("select", "board"): ("Select Board Member", True),
    ("trustee",): ("Trustee", True),
    ("vice", "chair"): ("Vice Chair", True),
    ("chair",): ("Chair", True),
    ("chairman",): ("Chair", True),
    ("chairwoman",): ("Chair", True),
    ("chairperson",): ("Chair", True),
    ("city", "manager"): ("City Manager", True),
    ("town", "manager"): ("Town Manager", True),
    ("county", "manager"): ("County Manager", True),
    ("city", "administrator"): ("City Administrator", True),
    ("town", "administrator"): ("Town Administrator", True),
    ("county", "administrator"): ("County Administrator", True),
    ("city", "attorney"): ("City Attorney", True),
    ("county", "attorney"): ("County Attorney", True),
    ("town", "attorney"): ("Town Attorney", True),
    ("city", "clerk"): ("City Clerk", True),
    ("town", "clerk"): ("Town Clerk", True),
    ("county", "clerk"): ("County Clerk", True),
    ("city", "engineer"): ("City Engineer", True),
    ("police", "chief"): ("Police Chief", True),
    ("fire", "chief"): ("Fire Chief", True),
    ("chief",): ("Chief", True),
    ("sheriff",): ("Sheriff", True),
    ("superintendent",): ("Superintendent", True),
    ("director",): ("Director", True),
    ("staff",): ("Staff", True),
    ("police",): ("Police", True),
    ("officer",): ("Officer", True),
    # Not an office: anyone may hold these, so the person is shown as a member of the public.
    ("committee", "member"): (None, False),
    ("board", "member"): (None, False),
    ("member",): (None, False),
    ("president",): (None, False),
    ("manager",): (None, False),
    ("attorney",): (None, False),
    ("resident",): (None, False),
    ("applicant",): (None, False),
    ("citizen",): (None, False),
    ("owner",): (None, False),
    ("developer",): (None, False),
    ("consultant",): (None, False),
    ("representative",): (None, False),
    ("speaker",): (None, False),
    ("public",): (None, False),
    ("unknown",): (None, False),
    ("person",): (None, False),
    ("role",): (None, False),
}
_PHRASES = sorted(_ROLE_PHRASES, key=len, reverse=True)

#: Words that mark a place rather than a name, when a slug has no role word.
_PLACE_WORDS = frozenset({"city", "county", "town", "village", "borough", "township", "of", "council", "common", "board",
                          "government", "commission", "committee", "the", "and"})
_NOT_A_NAME = frozenset({"unknown", "unidentified", "person", "speaker", "public", "resident", "member", "role", "sr", "jr"})

SCHOOL_RE = re.compile(r"(school|\bisd\b|\busd\b|board\s+of\s+ed|\bboe\b|student)", re.I)


@dataclass(frozen=True)
class ParsedSlug:
    name_tokens: tuple[str, ...]
    lead: Optional[str]  # the leading honorific or title, if any
    role_label: Optional[str]
    official: bool
    minor: bool


def _letters(s: str) -> list[str]:
    return re.findall(r"[a-z]+", (s or "").lower())


def parse_slug(slug: str, jurisdiction_name: Optional[str] = None) -> Optional[ParsedSlug]:
    """Split a speaker slug into name, role and whether the role is an office. None when nothing usable is in it."""
    toks = [t for t in (slug or "").lower().split("_") if t]
    while toks and toks[-1].isdigit():
        toks.pop()
    if not toks:
        return None
    if any(t in MINOR_TOKENS for t in toks):
        return ParsedSlug((), None, None, False, True)
    start = 0
    lead = None
    if toks[0] in HONORIFICS or toks[0] in LEAD_TITLES:
        lead, start = toks[0], 1
    role_at, role = None, None
    for i in range(start, len(toks)):
        for ph in _PHRASES:
            if tuple(toks[i : i + len(ph)]) == ph:
                role_at, role = i, ph
                break
        if role_at is not None:
            break
    if role_at is not None:
        name = toks[start:role_at]
    else:
        place = set(_letters(jurisdiction_name or "")) | _PLACE_WORDS
        if not jurisdiction_name:
            return None  # no role word and no place to tell the name from: unreliable
        name = list(toks[start:])
        while name and name[-1] in place:
            name.pop()
        if len(name) == len(toks[start:]):
            return None  # nothing matched the place: the name's end is a guess
    name = [t for t in name if t not in _NOT_A_NAME or t in ("sr", "jr")]
    if len([t for t in name if t not in ("sr", "jr")]) > 3:
        # More than first, middle and last: the slug runs a description into the name ("former_homeless_..."), so where
        # the name ends is a guess. Left out rather than risk showing a word that isn't a name.
        return None
    label, official = _ROLE_PHRASES.get(role, (None, False)) if role else (None, False)
    if lead in LEAD_TITLES:
        official = True
    if not [t for t in name if t not in ("sr", "jr")]:
        return None
    return ParsedSlug(tuple(name), lead, label if official else None, official, False)


def _title(tokens: Iterable[str]) -> str:
    out = []
    for t in tokens:
        out.append({"sr": "Sr.", "jr": "Jr."}.get(t, t[:1].upper() + t[1:]))
    return " ".join(out)


def _key(full_name: str) -> tuple[str, str]:
    toks = [t for t in _letters(full_name) if t not in ("sr", "jr", "ii", "iii", "iv")]
    return (toks[0], toks[-1]) if toks else ("", "")


class OfficialIndex:
    """Current officials of each government, for matching a slug's name to a canonical name and title."""

    def __init__(self, rows: Iterable[Any]):
        self.by_full: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        self.by_last: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for r in rows:
            r = dict(r)
            gov = (r.get("jurisdiction") or "").lower().removesuffix(" government").strip()
            st = (r.get("state_code") or "").upper()
            first, last = _key(r.get("full_name") or "")
            if not last:
                continue
            self.by_full.setdefault((st, gov, first, last), []).append(r)
            self.by_last.setdefault((st, gov, last), []).append(r)

    def match(self, state_code: Optional[str], jurisdiction: Optional[str], name: tuple[str, ...]) -> Optional[dict[str, Any]]:
        toks = [t for t in name if t not in ("sr", "jr")]
        if not toks or not jurisdiction:
            return None
        st, gov = (state_code or "").upper(), jurisdiction.lower().strip()
        hits = self.by_full.get((st, gov, toks[0], toks[-1]), []) if len(toks) > 1 else self.by_last.get((st, gov, toks[0]), [])
        return hits[0] if len(hits) == 1 else None


def person_for(
    slug: str,
    *,
    jurisdiction_name: Optional[str],
    state_code: Optional[str],
    school_board: bool,
    officials: Optional[OfficialIndex] = None,
) -> Optional[dict[str, Any]]:
    """{name, role, kind} for one slug, or None when it must not or cannot be shown."""
    p = parse_slug(slug, jurisdiction_name)
    if p is None or p.minor:
        return None
    hit = officials.match(state_code, jurisdiction_name, p.name_tokens) if officials else None
    if hit:
        return {"name": " ".join(str(hit["full_name"]).split()), "role": hit.get("title") or p.role_label, "kind": "official"}
    if p.official:
        lead = p.lead if p.lead in LEAD_TITLES and not p.role_label else None
        name = _title(([lead] if lead else []) + list(p.name_tokens))
        return {"name": name, "role": p.role_label, "kind": "official"}
    if school_board or p.lead in HONORIFICS:
        # No one but officials at a school board; an honorific and a surname is not a first name.
        return None
    toks = [t for t in p.name_tokens if t not in ("sr", "jr")]
    if len(toks) < 2:
        return None  # one word may be a surname: without a first and last name there is no "First L." to show
    return {"name": f"{_title([toks[0]])} {toks[-1][0].upper()}.", "role": None, "kind": "resident"}


def is_school_board(*texts: Optional[str], jurisdiction_type: Optional[str] = None) -> bool:
    return jurisdiction_type == "school_district" or any(t and SCHOOL_RE.search(t) for t in texts)


def _slugs(v: Any) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


def decision_people(
    competing_views: Any,
    *,
    speakers: Any = None,
    jurisdiction_name: Optional[str],
    state_code: Optional[str],
    school_board: bool,
    officials: Optional[OfficialIndex] = None,
) -> dict[str, Any]:
    """supported_by / opposed_by / spoke_on_it (officials first, each person once), the main view's label, and whether opposition is
    on record (None when the record has no competing views at all)."""
    cv = competing_views if isinstance(competing_views, dict) else {}
    dom = cv.get("dominant_view") if isinstance(cv.get("dominant_view"), dict) else {}
    counters = [c for c in (cv.get("counter_views") or []) if isinstance(c, dict)] if isinstance(cv.get("counter_views"), list) else []

    def people(slugs: list[str], seen: set[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in slugs:
            pr = person_for(s, jurisdiction_name=jurisdiction_name, state_code=state_code, school_board=school_board, officials=officials)
            if pr and pr["name"] not in seen:
                seen.add(pr["name"])
                out.append(pr)
        # Officials with a known role first, then other officials, then everyone else; the record's order within each.
        return sorted(out, key=lambda x: (x["kind"] != "official", x["role"] is None))

    seen: set[str] = set()
    supported = people(_slugs(dom.get("held_by")), seen)
    opposed = people([s for c in counters for s in _slugs(c.get("held_by"))], seen)
    # Everyone else the record says spoke on the item (decision_speakers), on no side.
    spoke = people(_slugs(speakers), seen)
    return {
        "supported_by": supported,
        "opposed_by": opposed,
        "spoke_on_it": spoke,
        "supported_view": (dom.get("view_label") or None) if dom else None,
        "opposition_recorded": (len(counters) > 0) if (dom or counters) else None,
    }


def vote_counts(vote_tally: Any) -> tuple[Optional[int], Optional[int]]:
    """(yes, no) from a recorded tally; both None unless yes is a real number."""
    vt = vote_tally if isinstance(vote_tally, dict) else {}
    yes, no = vt.get("yes"), vt.get("no")
    if not isinstance(yes, int):
        return None, None
    return yes, (no if isinstance(no, int) else None)


OFFICIALS_SQL = """
    SELECT full_name, title, jurisdiction, state_code
    FROM person_government
    WHERE office = 'government' AND coalesce(is_current, true)
      AND state_code = ANY($1::text[]) AND lower(jurisdiction) = ANY($2::text[])
"""


async def load_officials(conn: Any, places: Iterable[tuple[Optional[str], Optional[str]]]) -> Optional[OfficialIndex]:
    """Officials of the decisions' governments ("<jurisdiction> Government"), or None when person_government is missing."""
    import asyncpg
    from loguru import logger

    states = sorted({(s or "").upper() for s, j in places if s and j})
    govs = sorted({f"{j.lower().strip()} government" for s, j in places if s and j})
    if not states:
        return None
    try:
        return OfficialIndex(await conn.fetch(OFFICIALS_SQL, states, govs))
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("decision people: person_government unavailable ({}); slugs only", e)
        return None


DECISION_PEOPLE_SQL = """
    SELECT d.event_decision_id, d.headline, d.jurisdiction_name, d.jurisdiction_type, d.state_code,
           d.competing_views::text AS competing_views, d.vote_tally::text AS vote_tally,
           (SELECT ds.speaker_ids::text FROM decision_speakers ds WHERE ds.event_decision_id = d.event_decision_id) AS speaker_ids
    FROM event_decision d WHERE d.event_decision_id = ANY($1::text[])
"""


def _jsonb(raw: Any) -> Any:
    import json

    if raw is None or isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def people_fields(r: dict[str, Any], officials: Optional[OfficialIndex] = None) -> dict[str, Any]:
    """supported_by / opposed_by / supported_view / opposition_recorded / vote_yes / vote_no for one event_decision row
    (JSONB columns may arrive as TEXT: the pool has no JSONB codec)."""
    school = is_school_board(
        r.get("jurisdiction_name"), r.get("body_name"), r.get("headline"), jurisdiction_type=r.get("jurisdiction_type")
    )
    people = decision_people(
        _jsonb(r.get("competing_views")),
        speakers=_jsonb(r.get("speaker_ids")),
        jurisdiction_name=r.get("jurisdiction_name"),
        state_code=r.get("state_code"),
        school_board=school,
        officials=officials,
    )
    yes, no = vote_counts(_jsonb(r.get("vote_tally")))
    return {**people, "vote_yes": yes, "vote_no": no}
