"""Screen meeting transcripts with Jev before the paid Gemini analysis.

For each captioned video not yet screened, Jev answers three questions about the
transcript:

- ``meeting_kind`` (Choice): an official public meeting of a governing body, other
  government video (press conference, ceremony, training), or not government at all.
- ``has_decisions`` (Noul): the body votes on or approves something.
- ``mentions_data_center`` (Noul): a data center is discussed.

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
    "government_other": (
        "A government video that isn't a meeting of a governing body: a press conference, "
        "ceremony, proclamation event, training, town hall Q&A or public service announcement"
    ),
    "not_government": (
        "Not a government video: entertainment, sports, worship service, news commentary, "
        "a business or a private event"
    ),
}

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
    chunk_count                 integer NOT NULL,
    chunks_screened             integer NOT NULL,
    transcript_chars            integer NOT NULL,
    input_tokens                integer,
    answers                     jsonb NOT NULL,
    screened_at                 timestamptz NOT NULL DEFAULT now()
)
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE} (
    video_id, question_version, model, meeting_kind, meeting_kind_probabilities,
    has_decisions_p, mentions_data_center_p, chunk_count, chunks_screened,
    transcript_chars, input_tokens, answers, screened_at
) VALUES (
    %(video_id)s, %(question_version)s, %(model)s, %(meeting_kind)s,
    %(meeting_kind_probabilities)s, %(has_decisions_p)s, %(mentions_data_center_p)s,
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
    chunk_count: int
    chunks_screened: int
    transcript_chars: int
    input_tokens: int | None
    answers: list[dict[str, Any]]

    def row(self, *, screened_at: datetime | None = None) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "question_version": QUESTION_VERSION,
            "model": self.model,
            "meeting_kind": self.meeting_kind,
            "meeting_kind_probabilities": json.dumps(self.meeting_kind_probabilities),
            "has_decisions_p": self.has_decisions_p,
            "mentions_data_center_p": self.mentions_data_center_p,
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

    return {
        "meeting_kind": meeting_kind,
        "meeting_kind_probabilities": probs,
        "has_decisions_p": _max_noul("has_decisions"),
        "mentions_data_center_p": _max_noul("mentions_data_center"),
    }


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


def select_sql(
    *, states: Iterable[str], jurisdiction_id: str, rescreen: bool
) -> tuple[str, list[Any]]:
    """Captioned videos to screen, newest first. Already screened with the current
    questions are left out unless ``rescreen``."""
    where = ["t.has_transcript IS TRUE"]
    params: list[Any] = []
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    if state_list:
        where.append("e.state_code = ANY(%s)")
        params.append(state_list)
    if jurisdiction_id:
        where.append("e.jurisdiction_id = %s")
        params.append(jurisdiction_id)
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
            cur.execute(
                f"SELECT video_id FROM {TABLE} WHERE question_version = %s "
                "AND has_decisions_p IS NOT NULL AND has_decisions_p < %s",
                [QUESTION_VERSION, min_decisions_p],
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def gov_meeting_p_below(gov_meeting_p: float | None, min_meeting_p: float) -> bool:
    """True when a screen's government_meeting probability is strictly below the floor.

    ``None`` (missing key / null JSON) never skips — same spirit as unscreened."""
    return gov_meeting_p is not None and gov_meeting_p < min_meeting_p


def jev_skip_meeting_video_ids(database_url: str, min_meeting_p: float) -> set[str]:
    """Videos whose current screen puts ``P(government_meeting)`` below ``min_meeting_p``.

    Unscreened videos, older question wording, and null probabilities are never returned."""
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [TABLE])
            if cur.fetchone()[0] is None:
                return set()
            cur.execute(
                f"""
                SELECT video_id FROM {TABLE}
                WHERE question_version = %s
                  AND meeting_kind_probabilities ? 'government_meeting'
                  AND (meeting_kind_probabilities->>'government_meeting')::float < %s
                """,
                [QUESTION_VERSION, min_meeting_p],
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

    Each row is ``(video_id, P(government_meeting) | None)``. Null probability is never
    a skip. ``false_skip_rate`` is skip/n among this already-analyzed sample.
    """
    n = len(rows)
    out: list[dict[str, Any]] = []
    for t in thresholds:
        skip = sum(1 for _, p in rows if gov_meeting_p_below(p, t))
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
                 THEN (s.meeting_kind_probabilities->>'government_meeting')::float
                 ELSE NULL
               END AS gov_meeting_p
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
        "(questions {})",
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
        states=states, jurisdiction_id=args.jurisdiction_id, rescreen=args.rescreen
    )

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
        "keep/skip rates at P(government_meeting) thresholds; does not call Jev",
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
