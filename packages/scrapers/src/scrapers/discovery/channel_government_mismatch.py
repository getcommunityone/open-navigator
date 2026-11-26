"""
Detect a YouTube channel (or video) title that names a different government than
the jurisdiction it is being assigned to.

Why (#514, #515): discovery attributed channels by name alone.

* #515: the YouTube API name search for Bartow County, GA searched the bare word
  "Bartow" and accepted ``@CityOfBartow`` (City of Bartow, FL) at confidence 0.95.
* #514: a Valdosta, GA citizen-media channel whose videos are titled "BROOKS COUNTY
  BOARD OF COMMISSIONERS ...", "QUITMAN CITY COUNCIL ..." was filed under Gordon
  and Douglas, GA because LocalView had listed it under those places years earlier.

In both cases the stored channel title was the jurisdiction's *own* name (a loader
fallback), which then read as a government signal to verification. This module
supplies the guard used by name-based discovery (``pattern_match`` handle guesses
and ``youtube_api`` name search) and by the golden-channel gate: a channel whose
title or handle names another county, another city or another state is not assigned
on name evidence alone. Website-linked and domain-search channels are unaffected,
since they carry their own proof.

Pure functions only: no network, no database.

CLI (read-only scan of the warehouse, see ``main``)::

    python -m scrapers.discovery.channel_government_mismatch --min-videos 5
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

STATE_NAMES: dict[str, str] = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "DC": "district of columbia", "FL": "florida", "GA": "georgia", "HI": "hawaii",
    "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming",
}

# Full names that are too often something else (George Washington, Washington
# Street, Indiana County PA, Delaware County OH ...) to count as a state mention.
_AMBIGUOUS_STATE_NAMES = frozenset({"washington", "indiana", "delaware", "iowa", "ohio"})

# Two-letter codes that are also English words in all-caps titles (", IN THE ...").
_AMBIGUOUS_STATE_CODES = frozenset({"IN", "OR", "ME", "OK", "HI", "DE", "PA", "MA", "LA", "CO", "ID", "OH", "NE"})

# Words that end up in front of "County" / "City Council" without being a place.
_NOT_A_PLACE = frozenset(
    {
        "the", "a", "an", "this", "that", "our", "your", "their", "its", "each",
        "every", "per", "same", "local", "rural", "neighboring", "neighbouring",
        "other", "whole", "entire", "special", "regular", "joint", "called",
        "full", "new", "old", "and", "of", "for", "to", "in", "at", "on", "vs",
        "with", "by", "from", "meeting", "council", "commission", "board",
        "county", "city", "town", "village", "school", "public", "state",
        "district", "monthly", "annual", "weekly", "work", "session", "budget",
    }
)

_WORD = r"[a-z][a-z.'\-]*"
_COUNTY_RE = re.compile(rf"\b((?:{_WORD}\s+)?{_WORD})\s+county\b", re.I)
_COUNTY_OF_RE = re.compile(rf"\bcounty\s+of\s+({_WORD})", re.I)
_CITY_OF_RE = re.compile(rf"\b(?:city|town|village)\s+of\s+({_WORD}(?:\s+{_WORD})?)", re.I)
_CITY_BODY_RE = re.compile(
    rf"\b({_WORD})(?:\s*,\s*[a-z]{{2}}\.?)?\s+(?:city\s+(?:council|commission)|town\s+council)\b",
    re.I,
)
_COUNTY_BODY_RE = re.compile(
    r"\bcounty\s+(?:board\s+of\s+commissioners|commission(?:ers)?|board\s+of\s+supervisors)\b",
    re.I,
)
# Case-sensitive on purpose: ", GA" / ", FL." in the original text.
_STATE_ABBR_RE = re.compile(r",\s*([A-Z]{2})\b")
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
_HANDLE_RE = re.compile(r"youtube\.com/@([A-Za-z0-9_.\-]+)", re.I)


@dataclass(frozen=True)
class NamedGovernments:
    """Governments a piece of text names (lower-case place names)."""

    counties: frozenset[str]
    cities: frozenset[str]
    states: frozenset[str]
    names_county_body: bool


def _norm(name: str) -> str:
    name = re.sub(r"[^a-z' ]+", " ", (name or "").lower().replace("-", " "))
    return re.sub(r"\s+", " ", name).strip()


def _place(raw: str) -> Optional[str]:
    """Normalize a captured place name; None when it is not a place word."""
    words = [w for w in _norm(raw).split() if w]
    # "valdosta lowndes" from "Valdosta-Lowndes County": the county is the last word.
    while words and words[0] in _NOT_A_PLACE:
        words = words[1:]
    if not words or words[-1] in _NOT_A_PLACE:
        return None
    if " ".join(words) in STATE_NAMES.values() or (len(words) == 1 and len(words[0]) <= 2):
        return None
    return " ".join(words)


def _names_match(candidate: str, target: str) -> bool:
    """'regular brooks' matches 'brooks'; 'long' matches 'long beach'."""
    if not candidate or not target:
        return False
    return (
        candidate == target
        or candidate.endswith(" " + target)
        or target.endswith(" " + candidate)
        or target.startswith(candidate + " ")
        or candidate.startswith(target + " ")
    )


def handle_text(channel_url: str) -> str:
    """'https://www.youtube.com/@CityOfBartow' -> 'City Of Bartow' (else '')."""
    m = _HANDLE_RE.search(channel_url or "")
    if not m:
        return ""
    return _CAMEL_RE.sub(" ", m.group(1)).replace("_", " ").replace(".", " ").strip()


def named_governments(text: str) -> NamedGovernments:
    """Extract the counties, cities and states *text* names."""
    text = text or ""
    counties: set[str] = set()
    for m in _COUNTY_RE.finditer(text):
        place = _place(m.group(1))
        if place:
            # May keep a leading word ("valdosta lowndes"); _names_match compares
            # on the trailing words, so "lowndes" still matches.
            counties.add(place)
    for m in _COUNTY_OF_RE.finditer(text):
        place = _place(m.group(1))
        if place:
            counties.add(place)
    cities: set[str] = set()
    for m in _CITY_OF_RE.finditer(text):
        raw = m.group(1).split()
        place = _place(raw[0]) if raw else None
        if place:
            cities.add(place)
    for m in _CITY_BODY_RE.finditer(text):
        place = _place(m.group(1))
        if place:
            cities.add(place)
    states: set[str] = set()
    low = f" {_norm(text)} "
    for code, name in STATE_NAMES.items():
        if name in _AMBIGUOUS_STATE_NAMES:
            continue
        if f" {name} " in low and f" {name} county " not in low:
            states.add(code)
    for m in _STATE_ABBR_RE.finditer(text):
        code = m.group(1)
        if code in STATE_NAMES and code not in _AMBIGUOUS_STATE_CODES:
            states.add(code)
    return NamedGovernments(
        counties=frozenset(counties),
        cities=frozenset(cities),
        states=frozenset(states),
        names_county_body=bool(_COUNTY_BODY_RE.search(text)),
    )


def _target_token(jurisdiction_name: str) -> str:
    name = _norm(jurisdiction_name)
    for suffix in (" county", " parish", " borough", " city", " town", " village", " township"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    for prefix in ("city of ", "town of ", "village of ", "county of "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def title_names_other_government(
    title: str,
    *,
    jurisdiction_name: str,
    jurisdiction_type: str,
    state_code: str = "",
    channel_url: str = "",
) -> Optional[str]:
    """
    Return a reason when *title* (plus the channel's @handle, if given) names a
    government other than the target jurisdiction; ``None`` when it names the target
    or names no government at all.

    Reasons: ``names_other_state``, ``names_other_county``, ``names_city_not_county``,
    ``names_other_city``, ``names_county_government``.
    """
    text = " ".join(t for t in (title or "", handle_text(channel_url)) if t)
    if not text.strip():
        return None
    named = named_governments(text)
    target = _target_token(jurisdiction_name)
    jtype = (jurisdiction_type or "").strip().lower()
    state = (state_code or "").strip().upper()

    # A place named like a state (Oregon WI, Nevada IA, California City CA) names
    # that state every time it names itself.
    other_states = {
        code for code in named.states
        if code != state and not _names_match(STATE_NAMES[code], target)
        and STATE_NAMES[code] not in target.split()
    }
    if state and other_states:
        return "names_other_state"

    county_match = any(_names_match(c, target) for c in named.counties)
    city_match = any(_names_match(c, target) for c in named.cities)

    if jtype == "county":
        if county_match:
            return None
        if named.counties:
            return "names_other_county"
        if named.cities:
            return "names_city_not_county"
        return None

    if jtype in ("municipality", "city", "town", "village", "township"):
        if city_match:
            return None
        if named.cities:
            return "names_other_city"
        if named.names_county_body and named.counties:
            return "names_county_government"
        return None

    return None


def title_names_jurisdiction(
    title: str,
    *,
    jurisdiction_name: str,
    jurisdiction_type: str,
) -> bool:
    """True when *title* names this jurisdiction as a government (e.g. "Hamilton City
    Council ..." names Hamilton; "Bear Creek Christmas Parade" names nobody)."""
    named = named_governments(title or "")
    target = _target_token(jurisdiction_name or "")
    if not target:
        return False
    jtype = (jurisdiction_type or "").strip().lower()
    pool = named.counties if jtype == "county" else named.cities
    return any(_names_match(c, target) for c in pool)


def split_videos_naming_other_government(
    videos: Iterable[dict],
    *,
    jurisdiction_name: Optional[str],
    jurisdiction_type: str,
    state_code: str = "",
    siblings: Iterable[dict] = (),
) -> tuple[list[dict], list[tuple[dict, str]]]:
    """
    Split a shared channel's videos into ``(kept, skipped)`` for one jurisdiction (#777).

    A channel can serve several governments: a county news channel posts every
    town's council meetings (``49 County News.Net`` covers seven Marion County, AL
    towns). The loader filed every new video under the jurisdiction being
    refreshed, so Hamilton's meetings landed under Winfield.

    *siblings* are the other jurisdictions linked to the same channel (dicts with
    ``jurisdiction_id``, ``name``, ``jurisdiction_type``, ``state_code``). A video is
    skipped only when its title names another government **and** names exactly one
    sibling (``pick_named_sibling``): that sibling's refresh files it. ``skipped``
    holds ``(video, sibling jurisdiction_id)``. Everything else is kept, so a
    channel linked to one jurisdiction loses nothing, and a title naming a
    government that is not linked to the channel (a city channel posting county
    commission meetings) stays where it was.
    """
    sibs = list(siblings)
    kept: list[dict] = []
    skipped: list[tuple[dict, str]] = []
    for video in videos:
        title = video.get("title") or ""
        target = None
        if sibs and jurisdiction_name and title_names_other_government(
            title,
            jurisdiction_name=jurisdiction_name,
            jurisdiction_type=jurisdiction_type,
            state_code=state_code,
        ):
            target = pick_named_sibling(title, sibs)
        if target:
            skipped.append((video, target["jurisdiction_id"]))
        else:
            kept.append(video)
    return kept, skipped


def pick_named_sibling(title: str, siblings: Iterable[dict]) -> Optional[dict]:
    """
    Among the jurisdictions that share a channel (dicts with ``name``,
    ``jurisdiction_type``, ``state_code``), return the single one *title* names
    and does not contradict; ``None`` when none or more than one qualifies.
    Used to move a misfiled video to the sibling its title is about (#777).
    """
    hits = [
        s for s in siblings
        if title_names_jurisdiction(
            title, jurisdiction_name=s.get("name") or "", jurisdiction_type=s.get("jurisdiction_type") or ""
        )
        and not title_names_other_government(
            title,
            jurisdiction_name=s.get("name") or "",
            jurisdiction_type=s.get("jurisdiction_type") or "",
            state_code=s.get("state_code") or "",
        )
    ]
    return hits[0] if len(hits) == 1 else None


def real_channel_title(channel_title: Optional[str], jurisdiction_name: Optional[str]) -> Optional[str]:
    """
    The channel's own title, or ``None`` when *channel_title* is just the
    jurisdiction's name. The channel queries fill ``channel_title`` with the
    jurisdiction name when the real title is unknown; storing that in the channel
    catalog makes any channel look like the jurisdiction's own (#514, #515).
    """
    title = (channel_title or "").strip()
    if not title or title.lower() == "unknown channel":
        return None
    if jurisdiction_name and title.lower() == jurisdiction_name.strip().lower():
        return None
    return title


def channel_videos_name_other_government(
    video_titles: Iterable[str],
    *,
    jurisdiction_name: str,
    jurisdiction_type: str,
    state_code: str = "",
    min_named: int = 3,
    min_share: float = 0.6,
) -> Optional[tuple[int, int, int]]:
    """
    Video-level consistency check used by the scan: among titles that name *any*
    government, return ``(n_titles, n_named, n_other)`` when at least *min_named*
    name one and at least *min_share* of those name a government other than the
    filed jurisdiction; else ``None``.
    """
    n_titles = n_named = n_other = 0
    for t in video_titles:
        n_titles += 1
        named = named_governments(t or "")
        if not (named.counties or named.cities or named.states):
            continue
        n_named += 1
        if title_names_other_government(
            t,
            jurisdiction_name=jurisdiction_name,
            jurisdiction_type=jurisdiction_type,
            state_code=state_code,
        ):
            n_other += 1
    if n_named >= min_named and n_other / n_named >= min_share:
        return n_titles, n_named, n_other
    return None


_SCAN_SQL = """
    SELECT b.channel_id, b.jurisdiction_id, j.name, j.jurisdiction_type, j.state_code,
           array_agg(b.title ORDER BY b.video_id) AS titles
    FROM bronze.bronze_event_youtube b
    JOIN intermediate.int_jurisdictions j ON j.jurisdiction_id = b.jurisdiction_id
    WHERE b.channel_id IS NOT NULL AND b.title IS NOT NULL
    GROUP BY 1, 2, 3, 4, 5
    HAVING count(*) >= %s
"""


def scan(dsn: str, *, min_videos: int, min_named: int, min_share: float) -> list[dict]:
    """Read-only: channels whose video titles consistently name another government."""
    import psycopg2

    out: list[dict] = []
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(_SCAN_SQL, (min_videos,))
        for channel_id, jid, name, jtype, state, titles in cur.fetchall():
            hit = channel_videos_name_other_government(
                titles,
                jurisdiction_name=name,
                jurisdiction_type=jtype,
                state_code=state,
                min_named=min_named,
                min_share=min_share,
            )
            if not hit:
                continue
            n_titles, n_named, n_other = hit
            examples = [
                t for t in titles
                if title_names_other_government(
                    t, jurisdiction_name=name, jurisdiction_type=jtype, state_code=state
                )
            ][:3]
            out.append(
                {
                    "channel_id": channel_id,
                    "jurisdiction_id": jid,
                    "jurisdiction_name": name,
                    "state_code": state,
                    "videos": n_titles,
                    "titles_naming_a_government": n_named,
                    "titles_naming_another": n_other,
                    "examples": examples,
                }
            )
    out.sort(key=lambda r: (-r["titles_naming_another"], r["channel_id"]))
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    import json
    import os

    from loguru import logger

    parser = argparse.ArgumentParser(description="Read-only scan for channels filed under the wrong government.")
    parser.add_argument("--min-videos", type=int, default=5)
    parser.add_argument("--min-named", type=int, default=3)
    parser.add_argument("--min-share", type=float, default=0.6)
    parser.add_argument("--json", action="store_true", help="Print every hit as JSON lines")
    args = parser.parse_args(argv)

    dsn = os.environ.get("DATABASE_URL") or (
        "host={h} port={p} dbname=open_navigator user={u} password={pw}".format(
            h=os.environ.get("POSTGRES_HOST", "localhost"),
            p=os.environ.get("POSTGRES_PORT", "5433"),
            u=os.environ.get("POSTGRES_USER", "postgres"),
            pw=os.environ.get("POSTGRES_PASSWORD", ""),
        )
    )
    hits = scan(dsn, min_videos=args.min_videos, min_named=args.min_named, min_share=args.min_share)
    for h in hits:
        if args.json:
            print(json.dumps(h))
        else:
            logger.info(
                "{channel_id} filed under {jurisdiction_id} ({jurisdiction_name}, {state_code}): "
                "{titles_naming_another}/{titles_naming_a_government} government-naming titles name another; e.g. {ex}",
                ex=h["examples"][:1],
                **{k: v for k, v in h.items() if k != "examples"},
            )
    logger.success("{} channel/jurisdiction pairs flagged", len(hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
