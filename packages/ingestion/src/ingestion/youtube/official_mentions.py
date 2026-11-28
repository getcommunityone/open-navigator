"""Officials heard in a meeting, from the chair's call and the roll call (#1444).

Our meeting transcripts are YouTube captions with no speaker labels, and officials almost never introduce themselves
("my name is"), so the speaker layer (#1387) names residents but hardly ever an official. The chair and the clerk do
name them, though, at the moments they speak:

- **roll_call**: the clerk names a member and the member answers. "Voting with Councilor Howard. >> Yes." or
  "Commissioner Smith? >> Here."
- **chair_call**: the chair hands the floor to a member and the next turn starts. "Thank you, Zach. Mayor Maddox.
  >> Yes, sir." or "I recognize Councilor Busby" or "Councilor Faile, you're recognized."
- **self_intro**: a member names themself with their title. "This is Commissioner Smith."

This module finds those moments with regular expressions (no model, no network). It only looks for the members of
the meeting place's bodies (``gold.body_membership``, roster sources only, current or seated within two years), by
title plus surname, so a name heard in a meeting never makes anyone an official: a surname that isn't on the place's
roster is never matched. A surname two members share matches only with the first name too. A plain mention ("I spoke
with Councilor Busby") is not counted as the official being heard.

Writes ``bronze.bronze_meeting_official_mention`` (local warehouse only), one row per moment: video, character
offset, seconds (from the timed caption segments), the member (person_id when we hold one, and the roster name key),
the pattern, and up to 120 characters around the match. Privacy (AGENTS.md): only officials on a roster are named;
residents are never matched here.

Run::

    python -m ingestion.youtube.official_mentions                 # every place with a roster, last 730 days
    python -m ingestion.youtube.official_mentions --jurisdiction-id tuscaloosa_0177256 --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from loguru import logger

from ingestion.governance.roles import name_key
from ingestion.youtube.speaker_intros import _segment_map, _seconds_at, database_url

EXTRACTOR_VERSION = "official_mentions/1"
BRONZE_TABLE = "bronze.bronze_meeting_official_mention"

DDL = f"""
CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} (
    video_id           text        NOT NULL,
    char_offset        integer     NOT NULL,
    member_name_key    text        NOT NULL,
    jurisdiction_id    text        NOT NULL,
    person_id          text,
    member_name        text        NOT NULL,
    start_seconds      numeric(10, 3),
    pattern_id         text        NOT NULL,
    matched_text       text,
    extractor_version  text        NOT NULL,
    extracted_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bronze_meeting_official_mention_pkey PRIMARY KEY (video_id, char_offset, member_name_key)
);
CREATE INDEX IF NOT EXISTS bronze_meeting_official_mention_jur_idx ON {BRONZE_TABLE} (jurisdiction_id);
"""

# Titles the chair and clerk use, including the caption spellings we see ("councelor", "counselor").
TITLES = (
    r"council ?members?|council ?woman|council ?man|council ?lady|council ?person|councilor|councillor|councelor"
    r"|counselor|counsellor|council president|commissioner|alderman|alderwoman|alderperson|supervisor|mayor"
    r"|vice mayor|mayor pro tem|chairman|chairwoman|chairperson|vice chair|chair|president|trustee|selectman"
    r"|selectwoman|mr\.?|mrs\.?|ms\.?|miss|dr\.?|madam"
)

# What follows the name.
_ROLL_AFTER = re.compile(r"^[\s.,?!:;-]*(?:>>\s*)?(?:aye|nay|here|present)\b", re.I)
_YES_AFTER = re.compile(r"^[\s.,?!:;-]*(?:>>\s*)?(?:yes|no|yeah|yep)\b", re.I)
_TURN_AFTER = re.compile(r"^[\s.,?!:;-]*>>", re.I)
_RECOGNIZED_AFTER = re.compile(
    r"^[\s.,?!:;-]*(?:you(?:'re| are) recognized|go ahead|the floor is yours|you have the floor|please proceed)", re.I
)
# What comes before the title.
_RECOGNIZE_BEFORE = re.compile(
    r"(?:recogni[sz]e[sd]?|call(?:ing)? on|turn(?:ing)? it over to|over to|floor to|go to|hear from)\s*$", re.I
)
_VOTE_BEFORE = re.compile(r"(?:voting with|starting with|beginning with|roll call|call the roll)[\s,:]*$", re.I)
_SELF_BEFORE = re.compile(r"(?:this is|i'm|i am|my name is)\s*$", re.I)


@dataclass(frozen=True)
class Member:
    jurisdiction_id: str
    person_id: Optional[str]
    member_name: str
    key: str  # "first last"

    @property
    def first(self) -> str:
        return self.key.split(" ")[0]

    @property
    def last(self) -> str:
        return self.key.split(" ")[-1]


@dataclass(frozen=True)
class Mention:
    video_id: str
    char_offset: int
    member: Member
    start_seconds: Optional[float]
    pattern_id: str
    matched_text: str


def build_pattern(members: Sequence[Member]) -> Optional[re.Pattern[str]]:
    """One regex for a place: a title, an optional first name, then a roster surname."""
    surnames = sorted({m.last for m in members if len(m.last) >= 3}, key=len, reverse=True)
    if not surnames:
        return None
    firsts = sorted({m.first for m in members}, key=len, reverse=True)
    return re.compile(
        rf"\b(?P<title>{TITLES})\s+(?:(?P<first>{'|'.join(map(re.escape, firsts))})\s+)?"
        rf"(?P<last>{'|'.join(map(re.escape, surnames))})\b",
        re.I,
    )


def classify(text: str, start: int, end: int) -> Optional[str]:
    """roll_call / chair_call / self_intro for a title+name match at text[start:end], or None (a plain mention)."""
    after = text[end : end + 40]
    before = text[max(0, start - 40) : start]
    if _SELF_BEFORE.search(before):
        return "self_intro"
    if _VOTE_BEFORE.search(before) or _ROLL_AFTER.match(after):
        return "roll_call"
    if _RECOGNIZE_BEFORE.search(before) or _TURN_AFTER.match(after) or _RECOGNIZED_AFTER.match(after):
        return "chair_call"
    if _YES_AFTER.match(after):
        return "roll_call"
    return None


def find_mentions(video_id: str, raw_text: str, members: Sequence[Member], segments: Any = None) -> list[Mention]:
    """Every moment a roster member of this place is called on, answers a roll call or names themself."""
    pattern = build_pattern(members)
    if pattern is None or not raw_text:
        return []
    by_last: dict[str, list[Member]] = defaultdict(list)
    for m in members:
        by_last[m.last].append(m)
    seg_map = _segment_map(raw_text, segments)
    out: list[Mention] = []
    for match in pattern.finditer(raw_text):
        last = match.group("last").lower()
        first = (match.group("first") or "").lower()
        candidates = by_last.get(last, [])
        if first:
            candidates = [m for m in candidates if m.first == first] or ([] if len(candidates) > 1 else candidates)
        # Distinct people only: one person can hold two roles.
        people = {m.key: m for m in candidates}
        if len(people) != 1:
            continue  # unknown surname, or two members share it and no first name was said
        kind = classify(raw_text, match.start(), match.end())
        if kind is None:
            continue
        member = next(iter(people.values()))
        lo, hi = max(0, match.start() - 40), min(len(raw_text), match.end() + 60)
        out.append(
            Mention(
                video_id=video_id,
                char_offset=match.start(),
                member=member,
                start_seconds=_seconds_at(seg_map, match.start()),
                pattern_id=kind,
                matched_text=" ".join(raw_text[lo:hi].split())[:120],
            )
        )
    return out


# --------------------------------------------------------------------------------------------------------------------
# Warehouse
# --------------------------------------------------------------------------------------------------------------------

_MEMBERS_SQL = """
SELECT DISTINCT bm.jurisdiction_id, bm.person_id, bm.member_name
FROM gold.body_membership bm
JOIN gold.governing_body g ON g.governing_body_id = bm.governing_body_id
WHERE g.body_type <> 'legislature_chamber'
  AND bm.source IN ('officials', 'council_roster', 'legistar')
  AND (bm.is_current OR bm.end_date >= current_date - %(days)s)
  {extra}
"""

_VIDEOS_SQL = """
SELECT DISTINCT ON (mb.video_id) mb.video_id, mb.jurisdiction_id, t.raw_text, t.segments
FROM gold.meeting_body mb
JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = mb.video_id
WHERE mb.video_id IS NOT NULL
  AND mb.meeting_date >= current_date - %(days)s
  AND mb.jurisdiction_id = ANY(%(jids)s)
  AND t.raw_text IS NOT NULL
ORDER BY mb.video_id
"""


def load_members(conn: Any, *, days: int, jurisdiction_ids: Sequence[str]) -> dict[str, list[Member]]:
    extra = "AND bm.jurisdiction_id = ANY(%(jids)s)" if jurisdiction_ids else ""
    with conn.cursor() as cur:
        cur.execute(_MEMBERS_SQL.format(extra=extra), {"days": days, "jids": list(jurisdiction_ids)})
        rows = cur.fetchall()
    out: dict[str, dict[str, Member]] = defaultdict(dict)
    for jid, pid, name in rows:
        key = name_key(name)
        if not key:
            continue
        prev = out[jid].get(key)
        # One Member per person per place; keep the person_id when any row has it.
        if prev is None or (prev.person_id is None and pid):
            out[jid][key] = Member(jid, pid, name, key)
    return {jid: list(ms.values()) for jid, ms in out.items()}


def write_mentions(conn: Any, video_ids: Iterable[str], mentions: list[Mention]) -> None:
    from psycopg2.extras import execute_values

    vids = list(video_ids)
    with conn.cursor() as cur:
        if vids:
            cur.execute(f"DELETE FROM {BRONZE_TABLE} WHERE video_id = ANY(%s)", (vids,))
        if mentions:
            execute_values(
                cur,
                f"INSERT INTO {BRONZE_TABLE} (video_id, char_offset, member_name_key, jurisdiction_id, person_id, "
                "member_name, start_seconds, pattern_id, matched_text, extractor_version) VALUES %s "
                "ON CONFLICT (video_id, char_offset, member_name_key) DO NOTHING",
                [
                    (m.video_id, m.char_offset, m.member.key, m.member.jurisdiction_id, m.member.person_id,
                     m.member.member_name, m.start_seconds, m.pattern_id, m.matched_text, EXTRACTOR_VERSION)
                    for m in mentions
                ],
                page_size=1000,
            )


def run(*, days: int, jurisdiction_ids: Sequence[str], dry_run: bool, database: Optional[str] = None) -> dict[str, int]:
    import psycopg2

    conn = psycopg2.connect(database_url(database))
    conn.autocommit = True
    stats = {"jurisdictions": 0, "transcripts": 0, "with_mention": 0, "mentions": 0}
    try:
        if not dry_run:
            with conn.cursor() as cur:
                cur.execute(DDL)
        members = load_members(conn, days=days, jurisdiction_ids=jurisdiction_ids)
        stats["jurisdictions"] = len(members)
        conn.autocommit = False  # a server-side (named) cursor needs a transaction
        batch_vids: list[str] = []
        batch: list[Mention] = []
        with conn.cursor(name="official_mentions_src") as cur:
            cur.itersize = 100
            cur.execute(_VIDEOS_SQL, {"days": days, "jids": list(members)})
            for video_id, jid, raw_text, segments in cur:
                stats["transcripts"] += 1
                found = find_mentions(video_id, raw_text, members.get(jid, []), segments)
                if found:
                    stats["with_mention"] += 1
                    stats["mentions"] += len(found)
                batch_vids.append(video_id)
                batch += found
                if len(batch_vids) >= 200:
                    if not dry_run:
                        with psycopg2.connect(database_url(database)) as wconn:
                            write_mentions(wconn, batch_vids, batch)
                    batch_vids, batch = [], []
        if batch_vids and not dry_run:
            with psycopg2.connect(database_url(database)) as wconn:
                write_mentions(wconn, batch_vids, batch)
    finally:
        conn.close()
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=730, help="meetings in the last N days")
    p.add_argument("--jurisdiction-id", action="append", default=[], help="only this place (repeatable)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--database-url")
    args = p.parse_args(argv)
    stats = run(days=args.days, jurisdiction_ids=args.jurisdiction_id, dry_run=args.dry_run, database=args.database_url)
    logger.success("Official mentions: {}", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
