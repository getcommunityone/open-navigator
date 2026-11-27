"""
Speaker self-introductions in meeting transcripts (#1231).

Public commenters usually start by saying who they are on the record: "My name is Jane Doe and I live on Elm
Street", "I'm John Roe, a resident of Ward 3", "Good evening, Ana Ruiz here", or the chair calls them up: "our next
speaker is Sam Lee". Our transcripts are YouTube captions with no speaker labels, so these introductions are the only
free, deterministic evidence of who was speaking.

This module finds them with regular expressions (no model, no network) in
``bronze.bronze_event_youtube_transcript.raw_text`` and writes one row per introduction to
``bronze.bronze_meeting_speaker_intro``. It records only what the transcript says: the raw name tokens, where they
were said (character offset in ``raw_text``, which is ``event_documents.content``; and seconds when the transcript has
timed ``segments``), which pattern matched, and whether the speaker's next words say they are a student or a minor.

Privacy (AGENTS.md, "Privacy and data ethics"): the tokens stay in bronze (private warehouse). dbt turns them into the
served display form ("First L." for a private resident, the official's name and title when they match our officials
data) and drops names for students and minors. Nothing here looks anything up about a person.

Run (local warehouse only; reads ``OPEN_NAVIGATOR_DATABASE_URL``)::

    python -m ingestion.youtube.speaker_intros --story-passages   # videos behind the story-map quotes
    python -m ingestion.youtube.speaker_intros                    # every transcript
    python -m ingestion.youtube.speaker_intros --video-id abc123 --dry-run
"""

from __future__ import annotations

import argparse
import bisect
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Optional, Sequence

from loguru import logger

EXTRACTOR_VERSION = "speaker_intros/1"
BRONZE_TABLE = "bronze.bronze_meeting_speaker_intro"

# --------------------------------------------------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------------------------------------------------

_TOK = r"[A-Za-z][A-Za-z'’\-]{1,24}"
# Up to four tokens (a title, first, middle, last); trailing non-name words are trimmed afterwards.
_NAME = rf"(?P<name>{_TOK}(?:[ \t]+{_TOK}){{0,3}})"
# Caption fillers between the anchor and the name ("my name is uh Jane Doe").
_FILLER = r"(?:(?:uh|um|er|ah)[,.]?\s+)?"
_SEP = r"[,.;:!]?\s+"

PATTERNS: tuple[tuple[str, float, re.Pattern[str]], ...] = (
    # "my name is Jane Doe", "my name's Jane", "My name is, uh, Jane Doe"
    (
        "my_name_is",
        0.9,
        re.compile(rf"\bmy\s+name(?:'s|’s|\s+is)[,:]?\s+{_FILLER}{_NAME}", re.I),
    ),
    # "I'm Jane Doe and I live ...", "I am Jane Doe, a resident of ..."
    (
        "i_am_live",
        0.8,
        re.compile(
            rf"\b(?:i'm|i’m|i\s+am)\s+{_FILLER}{_NAME}{_SEP}(?:and\s+)?"
            r"(?:i\s+(?:live|reside)|i've\s+lived|i\s+have\s+lived|(?:i'm\s+|i\s+am\s+)?a\s+resident|resident\s+of)\b",
            re.I,
        ),
    ),
    # "this is Jane Doe from ...", "this is Jane Doe with the Elm Street association"
    (
        "this_is_from",
        0.6,
        re.compile(
            rf"\bthis\s+is\s+{_NAME}{_SEP}(?:from|with|calling\s+from|and\s+i\s+live|i\s+live)\b",
            re.I,
        ),
    ),
    # "Good evening, Jane Doe here", "good evening Jane Doe, I live on ..."
    (
        "greeting_name",
        0.6,
        re.compile(
            rf"\bgood\s+(?:evening|morning|afternoon)[,.!]?\s+{_NAME}{_SEP}"
            r"(?:here\b|i\s+live|i\s+reside|resident\b|from\b|\d{2,5}\s+[A-Za-z])",
            re.I,
        ),
    ),
    # The chair calling a speaker: "our next speaker is Jane Doe", "first speaker will be Jane Doe"
    (
        "next_speaker",
        0.5,
        re.compile(
            rf"\b(?:next|first|last|final)\s+speaker\s+(?:is|will\s+be|we\s+have\s+is|i\s+have\s+is)[,:]?\s+{_NAME}",
            re.I,
        ),
    ),
)

# Fast path: a full-text regex scan is ~1 MB/s, too slow for 5 GB of captions. Each pattern is only tried in a window
# around a cheap literal anchor (lower-cased str.find): (anchor words, chars before, chars after).
ANCHORS: dict[str, tuple[tuple[str, ...], int, int]] = {
    "my_name_is": (("name",), 12, 160),
    "i_am_live": (("live", "resid"), 140, 20),
    "this_is_from": (("this",), 2, 160),
    "greeting_name": (("good",), 2, 180),
    "next_speaker": (("speaker",), 12, 160),
}


def _anchor_positions(low: str, words: Sequence[str]) -> list[int]:
    out: list[int] = []
    for w in words:
        k = low.find(w)
        while k != -1:
            out.append(k)
            k = low.find(w, k + 1)
    return sorted(out)


# Courtesy titles and offices that can lead a name ("my name is Dr. Jane Doe", "this is Councilman Joe Roe").
TITLES = frozenset(
    """
    dr doctor mr mrs ms miss mister reverend rev pastor father sister brother
    councilman councilwoman councilmember councilor councillor alderman alderwoman commissioner
    mayor judge sheriff chief captain officer lieutenant sergeant professor
    """.split()
)

# Words that are never a first name or surname in this position: function words, fillers, places, roles and the
# words a sentence carries on with ("my name is on the list", "I'm here from", "this is the city").
STOPWORDS = frozenset(
    """
    a an the and or but nor so yet for of to in on at by with from into onto about above after again against all
    also am any are as be because been before being below between both can cannot could did do does doing done
    down during each few further had has have having he her here hers herself him himself his how i if is it its
    itself just me more most my myself no not now off once only other our ours ourselves out over own same she
    should some such than that their theirs them themselves then there these they this those through too under
    until up very was we were what when where which while who whom why will would you your yours yourself
    yourselves um uh er ah oh okay ok yes yeah well like really actually basically sure thanks thank please sorry
    hello hi hey good evening morning afternoon night everyone everybody all folks guys ladies gentlemen
    sir madam maam mayor council councilman councilwoman councilmember councilmembers councilor councilors chair
    chairman chairwoman chairperson vice president commissioner commissioners board members member staff city
    town county village state township district school public resident residents citizen citizens neighbor
    neighbors speaker speakers next first last final second third item agenda motion meeting hearing comment
    comments name names number address street avenue road drive lane ward going gonna gotta wanna trying try
    want wanted here's there's it's that's i'm i've i'll i'd we're we've you're they're he's she's let's
    calling call called speaking speak spoke talk talking asking ask asked coming come came glad happy proud
    excited honored pleased grateful here today tonight tomorrow yesterday now just still again back currently
    retired new old long life lifelong born raised also both one two three four five six seven eight nine ten
    little bit lot very much many more most least whole entire part partner owner owners business businesses
    representing represent representative director manager executive president secretary treasurer attorney
    lawyer engineer planner applicant developer consultant pastor parent parents mom mother dad father
    teacher student students senior seniors junior juniors freshman sophomore kid kids child children son
    daughter wife husband family member live living lived reside residing located local area community
    neighborhood behalf regarding concerning re against support supporting opposed opposition favor
    unable able sure aware afraid concerned worried disappointed sad sorry tired confused curious
    somewhat different similar separate consistent exempt important critical
    followed following running economic development background welcome welcoming presenting addressing regard regards thereof
    not never nothing something anything everything someone anyone everyone nobody somebody anybody
    mr mrs ms dr miss mister
    """.split()
)

# Said by the speaker in the words after the introduction: suppress the name (minors and students are never named).
_MINOR_RE = re.compile(
    r"\b(?:student|students|freshman|sophomore|junior|juniors|senior\s+at|grader|"
    r"(?:\d{1,2}(?:st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)"
    r"\s+grade|high\s+school|middle\s+school|elementary|junior\s+high|"
    r"(?:i'm|i’m|i\s+am)\s+(?:(?:[1-9]|1[0-7])|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen)\s+(?:years?\s+old|yrs?\s+old)|"
    r"(?:i'm|i’m|i\s+am)\s+(?:a\s+)?(?:minor|kid|child|teen|teenager))\b",
    re.I,
)
MINOR_WINDOW_CHARS = 300


@dataclass(frozen=True)
class SpeakerIntro:
    """One self-introduction (or chair call) found in a transcript."""

    video_id: str
    char_offset: int
    pattern_id: str
    confidence: float
    name_tokens: tuple[str, ...]
    title_token: Optional[str]
    matched_text: str
    mentions_minor: bool
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None


def clean_name_tokens(raw: str) -> tuple[Optional[str], tuple[str, ...]]:
    """(leading title or None, the name tokens) from a matched name, or (title, ()) when it isn't a name.

    Trailing words that aren't names are trimmed ("Jane Doe and" → Jane Doe); a first word that isn't a name rejects
    the whole match ("on the list", "here from"). Tokens keep the transcript's spelling, lower-cased.
    """
    tokens = [t.strip("'’-").lower() for t in raw.split()]
    tokens = [t for t in tokens if t]
    title: Optional[str] = None
    while tokens and tokens[0].rstrip(".") in TITLES:
        title = title or tokens[0].rstrip(".")
        tokens.pop(0)
    kept: list[str] = []
    for t in tokens:
        if t in STOPWORDS or t in TITLES or len(t) < 2 or not re.fullmatch(r"[a-z][a-z'’\-]*", t):
            break
        kept.append(t)
    if title and len(kept) == 1:
        # "Dr. Smith", "Councilman Roe": a surname alone can't make "First L." and must not pass as a first name.
        kept = []
    return title, tuple(kept[:3])


def _segment_map(raw_text: str, segments: Any) -> Optional[tuple[list[int], list[dict[str, Any]]]]:
    """Character start of each timed segment in ``raw_text``, when ``raw_text`` is exactly the segments joined by
    single spaces (true for every ``segments`` row in the warehouse). None otherwise: seconds stay unknown."""
    if not isinstance(segments, list) or not segments:
        return None
    segs = [s for s in segments if isinstance(s, dict)]
    texts = [str(s.get("text") or "") for s in segs]
    if " ".join(texts) != raw_text:
        return None
    starts: list[int] = []
    pos = 0
    for t in texts:
        starts.append(pos)
        pos += len(t) + 1
    return starts, segs


def _seconds_at(seg_map: Optional[tuple[list[int], list[dict[str, Any]]]], offset: int) -> Optional[float]:
    if seg_map is None:
        return None
    starts, segs = seg_map
    i = bisect.bisect_right(starts, offset) - 1
    if i < 0:
        return None
    try:
        return round(float(segs[i].get("start")), 3)
    except (TypeError, ValueError):
        return None


def _end_seconds_at(seg_map: Optional[tuple[list[int], list[dict[str, Any]]]], offset: int) -> Optional[float]:
    if seg_map is None:
        return None
    starts, segs = seg_map
    i = bisect.bisect_right(starts, offset) - 1
    if i < 0:
        return None
    try:
        start = float(segs[i].get("start"))
        dur = float(segs[i].get("duration") or 0.0)
        return round(start + dur, 3)
    except (TypeError, ValueError):
        return None


def find_intros(video_id: str, raw_text: str, segments: Any = None) -> list[SpeakerIntro]:
    """Every self-introduction in one transcript, in order. Pure function: no I/O."""
    if not raw_text:
        return []
    seg_map = _segment_map(raw_text, segments)
    found: dict[tuple[int, str], SpeakerIntro] = {}
    low = raw_text.lower()
    n = len(raw_text)
    for pattern_id, confidence, rx in PATTERNS:
        words, before, after = ANCHORS[pattern_id]
        matches = []
        for k in _anchor_positions(low, words):
            m = rx.search(raw_text, max(0, k - before), min(n, k + after))
            if m is not None:
                matches.append(m)
        for m in matches:
            title, tokens = clean_name_tokens(m.group("name"))
            if not tokens:
                continue
            if pattern_id == "this_is_from" and len(tokens) != 2:
                # "this is separate from", "this is Carolina Environmental Systems with": only a first and last name.
                continue
            offset = m.start()
            # End of the last kept name token (the matched group can run on into "and", "here", ...).
            name_end = m.end("name")
            for tok in re.finditer(r"\S+", m.group("name")):
                if tok.group(0).strip("'\u2019-.").lower() == tokens[-1]:
                    name_end = m.start("name") + tok.end()
                    break
            window = raw_text[m.start("name") : name_end + MINOR_WINDOW_CHARS]
            key = (offset, pattern_id)
            found[key] = SpeakerIntro(
                video_id=video_id,
                char_offset=offset,
                pattern_id=pattern_id,
                confidence=confidence,
                name_tokens=tokens,
                title_token=title,
                matched_text=" ".join(m.group(0).split())[:200],
                mentions_minor=bool(_MINOR_RE.search(window)),
                start_seconds=_seconds_at(seg_map, offset),
                end_seconds=_end_seconds_at(seg_map, name_end),
            )
    return sorted(found.values(), key=lambda r: (r.char_offset, r.pattern_id))


# --------------------------------------------------------------------------------------------------------------------
# Warehouse I/O
# --------------------------------------------------------------------------------------------------------------------

DDL = f"""
CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} (
    video_id          text        NOT NULL,
    char_offset       integer     NOT NULL,
    pattern_id        text        NOT NULL,
    start_seconds     numeric(10, 3),
    end_seconds       numeric(10, 3),
    confidence        numeric(3, 2) NOT NULL,
    name_tokens       text[]      NOT NULL,
    title_token       text,
    mentions_minor    boolean     NOT NULL DEFAULT false,
    matched_text      text        NOT NULL,
    extractor_version text        NOT NULL,
    extracted_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, char_offset, pattern_id)
)
"""

_ANCHOR_SQL = r"(my name|speaker (is|will be)|i live|i reside|resident of|good (evening|morning|afternoon)|this is)"

_SOURCE_SQL = f"""
SELECT t.video_id, t.raw_text, t.segments
FROM bronze.bronze_event_youtube_transcript t
WHERE t.raw_text IS NOT NULL AND t.raw_text ~* '{_ANCHOR_SQL}'
  {{extra}}
ORDER BY t.video_id
"""

_STORY_VIDEOS_SQL = """
  AND t.video_id IN (
      SELECT video_id FROM gold.topic_transcript_link
      UNION SELECT video_id FROM gold.data_center_meeting_mention
  )
"""


def database_url(explicit: Optional[str] = None) -> str:
    """The local warehouse write DSN: ``--database-url``, else ``OPEN_NAVIGATOR_DATABASE_URL`` (loaded from .env when
    python-dotenv is installed). Never a production Neon URL."""
    if not explicit:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:  # pragma: no cover
            pass
    url = (explicit or os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("Set OPEN_NAVIGATOR_DATABASE_URL (local warehouse) or pass --database-url")
    if "neon.tech" in url and url == (os.getenv("NEON_DATABASE_URL") or "").strip():
        raise SystemExit("Refusing to write to the production Neon database")
    return url


def iter_transcripts(conn: Any, *, story_passages: bool, video_ids: Sequence[str], limit: Optional[int]) -> Iterator[dict[str, Any]]:
    extra = ""
    params: list[Any] = []
    if video_ids:
        extra += " AND t.video_id = ANY(%s)"
        params.append(list(video_ids))
    if story_passages:
        extra += _STORY_VIDEOS_SQL
    sql = _SOURCE_SQL.format(extra=extra)
    if limit:
        sql += f" LIMIT {int(limit)}"
    with conn.cursor(name="speaker_intro_src") as cur:
        cur.itersize = 200
        cur.execute(sql, params)
        for video_id, raw_text, segments in cur:
            yield {"video_id": video_id, "raw_text": raw_text, "segments": segments}


def write_intros(conn: Any, video_ids: Iterable[str], intros: list[SpeakerIntro]) -> None:
    """Replace the rows for these videos (idempotent re-runs, and a rule change can drop a stale match)."""
    from psycopg2.extras import execute_values

    vids = list(video_ids)
    with conn.cursor() as cur:
        if vids:
            cur.execute(f"DELETE FROM {BRONZE_TABLE} WHERE video_id = ANY(%s)", (vids,))
        if intros:
            execute_values(
                cur,
                f"INSERT INTO {BRONZE_TABLE} (video_id, char_offset, pattern_id, start_seconds, end_seconds, "
                "confidence, name_tokens, title_token, mentions_minor, matched_text, extractor_version) VALUES %s",
                [
                    (
                        r.video_id,
                        r.char_offset,
                        r.pattern_id,
                        r.start_seconds,
                        r.end_seconds,
                        r.confidence,
                        list(r.name_tokens),
                        r.title_token,
                        r.mentions_minor,
                        r.matched_text,
                        EXTRACTOR_VERSION,
                    )
                    for r in intros
                ],
                page_size=1000,
            )


@dataclass
class RunStats:
    transcripts: int = 0
    with_intro: int = 0
    intros: int = 0
    by_pattern: dict[str, int] = field(default_factory=dict)
    minor_flagged: int = 0


def run(
    *,
    url: str,
    story_passages: bool = False,
    video_ids: Sequence[str] = (),
    limit: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 500,
) -> RunStats:
    import psycopg2

    stats = RunStats()
    read_conn = psycopg2.connect(url)
    write_conn = None if dry_run else psycopg2.connect(url)
    try:
        if write_conn is not None:
            with write_conn.cursor() as cur:
                cur.execute(DDL)
            write_conn.commit()
        batch_vids: list[str] = []
        batch_rows: list[SpeakerIntro] = []
        for row in iter_transcripts(read_conn, story_passages=story_passages, video_ids=video_ids, limit=limit):
            intros = find_intros(row["video_id"], row["raw_text"], row["segments"])
            stats.transcripts += 1
            if intros:
                stats.with_intro += 1
            stats.intros += len(intros)
            stats.minor_flagged += sum(1 for r in intros if r.mentions_minor)
            for r in intros:
                stats.by_pattern[r.pattern_id] = stats.by_pattern.get(r.pattern_id, 0) + 1
            batch_vids.append(row["video_id"])
            batch_rows.extend(intros)
            if len(batch_vids) >= batch_size:
                if write_conn is not None:
                    write_intros(write_conn, batch_vids, batch_rows)
                    write_conn.commit()
                logger.info("{:,} transcripts scanned, {:,} intros", stats.transcripts, stats.intros)
                batch_vids, batch_rows = [], []
        if batch_vids and write_conn is not None:
            write_intros(write_conn, batch_vids, batch_rows)
            write_conn.commit()
    finally:
        read_conn.close()
        if write_conn is not None:
            write_conn.close()
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--database-url", help="Local warehouse DSN (default: OPEN_NAVIGATOR_DATABASE_URL)")
    p.add_argument("--story-passages", action="store_true", help="Only videos behind topic and data-center story quotes")
    p.add_argument("--video-id", action="append", default=[], help="Only this video (repeatable)")
    p.add_argument("--limit", type=int, help="Stop after N transcripts")
    p.add_argument("--dry-run", action="store_true", help="Scan and count; write nothing")
    args = p.parse_args(argv)
    stats = run(
        url=database_url(args.database_url),
        story_passages=args.story_passages,
        video_ids=args.video_id,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    logger.success(
        "{:,} transcripts, {:,} with an introduction, {:,} introductions ({:,} flagged student/minor); by pattern {}",
        stats.transcripts,
        stats.with_intro,
        stats.intros,
        stats.minor_flagged,
        dict(sorted(stats.by_pattern.items())),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
