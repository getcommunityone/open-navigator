"""Short generative blurb for Jev keepers that lack full Gemini Part‑1 (#705).

Jev cannot write prose. After a video passes the meeting-kind keep-score, this
module asks a cheap chat model for 1–2 factual sentences and stores them in
``bronze.bronze_transcript_blurb_light``. Full Part‑1 ``meeting_summary`` still
wins in the UI when present.

Usage::

    python -m llm.typesafe.light_blurb --state AL --limit 20 --dry-run
    python -m llm.typesafe.light_blurb --state AL --limit 20
    python -m llm.typesafe.light_blurb --jurisdiction-id tuscaloosa_0177256
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from loguru import logger

from llm.prompt_version import prompt_sha256
from llm.typesafe.screen_transcripts import (
    MEETING_KEEP_KIND_KEYS,
    TABLE as SCREEN_TABLE,
    meeting_keep_p,
)
from llm.usage.calls import llm_call_context

TABLE = "bronze.bronze_transcript_blurb_light"
DEFAULT_KEEP_T = 0.6
DEFAULT_MAX_TRANSCRIPT_CHARS = 12_000
DEFAULT_MAX_OUTPUT_TOKENS = 256
# UI / excerpt helper: below this, YouTube description is usually boilerplate.
MIN_DESCRIPTION_CHARS = 120
EXTRACT_SNIPPET_CHARS = 400

SYSTEM_INSTRUCTION = (
    "You write a very short factual blurb about a public meeting transcript. "
    "Use only information supported by the provided text. Do not invent votes, "
    "dollar amounts, speaker names, or outcomes. If the excerpt is too thin, "
    "say only what is clearly present."
)

USER_PROMPT_PREFIX = (
    "Write 1–2 short sentences summarizing what this public meeting appears to "
    "cover. No invented votes, amounts, or names.\n\n"
)

PROMPT_SHA256 = prompt_sha256(SYSTEM_INSTRUCTION + "\n" + USER_PROMPT_PREFIX)

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    video_id        text PRIMARY KEY,
    blurb_text      text NOT NULL,
    model           text NOT NULL,
    prompt_sha256   text NOT NULL,
    input_tokens    integer,
    output_tokens   integer,
    created_at      timestamptz NOT NULL DEFAULT now()
)
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE} (
    video_id, blurb_text, model, prompt_sha256, input_tokens, output_tokens, created_at
) VALUES (
    %(video_id)s, %(blurb_text)s, %(model)s, %(prompt_sha256)s,
    %(input_tokens)s, %(output_tokens)s, %(created_at)s
)
ON CONFLICT (video_id) DO UPDATE SET
    blurb_text = EXCLUDED.blurb_text,
    model = EXCLUDED.model,
    prompt_sha256 = EXCLUDED.prompt_sha256,
    input_tokens = EXCLUDED.input_tokens,
    output_tokens = EXCLUDED.output_tokens,
    created_at = EXCLUDED.created_at
"""


@dataclass(frozen=True)
class BlurbResult:
    video_id: str
    blurb_text: str
    model: str
    prompt_sha256: str
    input_tokens: int | None
    output_tokens: int | None

    def row(self, *, created_at: datetime | None = None) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "blurb_text": self.blurb_text,
            "model": self.model,
            "prompt_sha256": self.prompt_sha256,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "created_at": created_at or datetime.now(UTC),
        }


def choose_light_excerpt(
    *,
    meeting_summary: str | None = None,
    blurb_text: str | None = None,
    youtube_description: str | None = None,
    transcript_snippet: str | None = None,
    min_description_chars: int = MIN_DESCRIPTION_CHARS,
) -> str | None:
    """UI excerpt precedence (#705). Never invents text — returns None if nothing usable."""
    summary = (meeting_summary or "").strip()
    if summary:
        return summary
    blurb = (blurb_text or "").strip()
    if blurb:
        return blurb
    desc = (youtube_description or "").strip()
    if len(desc) >= min_description_chars:
        return desc
    snip = (transcript_snippet or "").strip()
    if snip:
        return snip
    return None


def extractive_snippet(text: str, *, max_chars: int = EXTRACT_SNIPPET_CHARS) -> str:
    """First usable window of transcript/description text (no model)."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars]
    # Prefer a word boundary so tiles don't end mid-token.
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def build_user_prompt(
    *,
    title: str | None,
    description: str | None,
    transcript: str,
    max_transcript_chars: int = DEFAULT_MAX_TRANSCRIPT_CHARS,
) -> str:
    parts = [USER_PROMPT_PREFIX]
    if (title or "").strip():
        parts.append(f"Title: {title.strip()}\n")
    desc = (description or "").strip()
    if desc:
        parts.append(f"YouTube description:\n{desc[:2000]}\n\n")
    body = " ".join((transcript or "").split())
    if len(body) > max_transcript_chars:
        body = body[:max_transcript_chars] + "…"
    parts.append(f"Transcript excerpt:\n{body}")
    return "".join(parts)


def _clean_blurb(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip()
    # Drop wrapping quotes the model sometimes adds.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1].strip()
    return cleaned


def generate_blurb(
    *,
    api_key: str,
    model: str,
    video_id: str,
    title: str | None,
    description: str | None,
    transcript: str,
    max_transcript_chars: int = DEFAULT_MAX_TRANSCRIPT_CHARS,
) -> BlurbResult | None:
    """One cheap chat call. Returns ``None`` when the model yields empty text."""
    from llm.gemini.genai_text_client import call_gemini_text

    user_text = build_user_prompt(
        title=title,
        description=description,
        transcript=transcript,
        max_transcript_chars=max_transcript_chars,
    )
    with llm_call_context(stage="light_blurb", video_id=video_id):
        result = call_gemini_text(
            api_key=api_key,
            model=model,
            user_text=user_text,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.1,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_budget=0,
        )
    blurb = _clean_blurb(result.text)
    if not blurb:
        return None
    usage = result.usage
    return BlurbResult(
        video_id=video_id,
        blurb_text=blurb,
        model=result.model or model,
        prompt_sha256=PROMPT_SHA256,
        input_tokens=getattr(usage, "input_token_count", None) if usage else None,
        output_tokens=getattr(usage, "output_token_count", None) if usage else None,
    )


def _database_url(explicit: str) -> str:
    from llm.gemini.analyze_backlog import _resolve_database_url

    return _resolve_database_url(explicit)


def _segment_texts(row: dict[str, Any]) -> list[str]:
    from llm.typesafe.screen_transcripts import _segment_texts as _seg

    return _seg(row)


def _transcript_blob(row: dict[str, Any]) -> str:
    parts = _segment_texts(row)
    if parts:
        return " ".join(parts)
    raw = row.get("raw_text") or row.get("caption_text_timed") or ""
    return str(raw)


def select_keeper_sql(
    *,
    states: Iterable[str],
    jurisdiction_id: str,
    keep_t: float,
    include_analyzed: bool,
) -> tuple[str, list[Any]]:
    """Keepers (keep-score ≥ T) with transcript, no blurb yet.

    By default skips videos that already have Gemini ``policy_analysis_at``.
    """
    where = [
        "t.has_transcript IS TRUE",
        "s.video_id IS NOT NULL",
        (
            "("
            + " + ".join(
                f"COALESCE((s.meeting_kind_probabilities->>'{k}')::float, 0)"
                for k in MEETING_KEEP_KIND_KEYS
            )
            + ") >= %s"
        ),
        f"NOT EXISTS (SELECT 1 FROM {TABLE} b WHERE b.video_id = t.video_id)",
    ]
    params: list[Any] = [keep_t]
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    if state_list:
        where.append("e.state_code = ANY(%s)")
        params.append(state_list)
    if jurisdiction_id:
        where.append("e.jurisdiction_id = %s")
        params.append(jurisdiction_id)
    if not include_analyzed:
        where.append("e.policy_analysis_at IS NULL")

    sql = f"""
        SELECT DISTINCT ON (t.video_id)
               t.video_id, t.segments, t.caption_text_timed, t.raw_text,
               e.title, e.description, e.published_at, e.state_code, e.jurisdiction_id,
               s.meeting_kind_probabilities
        FROM bronze.bronze_event_youtube_transcript t
        JOIN bronze.bronze_event_youtube e ON e.video_id = t.video_id
        JOIN {SCREEN_TABLE} s ON s.video_id = t.video_id
        WHERE {" AND ".join(where)}
        ORDER BY t.video_id, e.published_at DESC NULLS LAST
    """
    return (
        f"SELECT * FROM ({sql}) v ORDER BY published_at DESC NULLS LAST LIMIT %s",
        params,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    from llm.gemini.genai_text_client import (
        default_flash_lite_model,
        ensure_valid_gemini_api_key,
        resolve_gemini_api_key,
    )

    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    sql, params = select_keeper_sql(
        states=states,
        jurisdiction_id=args.jurisdiction_id or "",
        keep_t=float(args.keep_t),
        include_analyzed=bool(args.include_analyzed),
    )

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
            # Screen table must exist for the join; do not create it here.
            cur.execute("SELECT to_regclass(%s)", [SCREEN_TABLE])
            if cur.fetchone()[0] is None:
                raise SystemExit(
                    f"{SCREEN_TABLE} is missing — run "
                    "`python -m llm.typesafe.screen_transcripts` first"
                )
        conn.commit()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, [*params, args.limit])
            rows = cur.fetchall()
    finally:
        conn.close()

    model = (args.model or "").strip() or default_flash_lite_model()
    summary = {
        "selected": len(rows),
        "written": 0,
        "empty": 0,
        "failed": 0,
        "model": model,
        "keep_t": float(args.keep_t),
    }
    logger.info(
        "{:,} keeper(s) need a light blurb (keep_t={}, model={})",
        len(rows),
        args.keep_t,
        model,
    )
    if args.dry_run:
        logger.success("Dry run: nothing sent.")
        return summary

    # DeepSeek and Anthropic keys are resolved inside call_gemini_text; Gemini needs a pool key.
    if model.startswith(("deepseek", "claude-")):
        api_key = resolve_gemini_api_key() or "no-gemini-key"
    else:
        repo = Path(__file__).resolve().parents[5]
        api_key = ensure_valid_gemini_api_key(
            env_path=repo / ".env",
            model=model,
        )

    conn = psycopg2.connect(database_url)
    try:
        for i, row in enumerate(rows, 1):
            vid = row["video_id"]
            transcript = _transcript_blob(row)
            if not transcript.strip():
                summary["empty"] += 1
                logger.warning("[{}/{}] {} — empty transcript", i, len(rows), vid)
                continue
            # Sanity: keep-score still passes (SQL already filtered).
            keep = meeting_keep_p(row.get("meeting_kind_probabilities"))
            if keep is None or keep < float(args.keep_t):
                summary["empty"] += 1
                continue
            try:
                result = generate_blurb(
                    api_key=api_key,
                    model=model,
                    video_id=vid,
                    title=row.get("title"),
                    description=row.get("description"),
                    transcript=transcript,
                    max_transcript_chars=int(args.max_transcript_chars),
                )
            except Exception as exc:
                summary["failed"] += 1
                logger.warning("[{}/{}] {} failed: {}", i, len(rows), vid, exc)
                continue
            if result is None:
                summary["empty"] += 1
                logger.warning("[{}/{}] {} — empty model blurb (not stored)", i, len(rows), vid)
                continue
            with conn.cursor() as cur:
                cur.execute(UPSERT_SQL, result.row())
            conn.commit()
            summary["written"] += 1
            logger.info(
                "[{}/{}] {} blurb={}",
                i,
                len(rows),
                vid,
                result.blurb_text[:120],
            )
    finally:
        conn.close()

    logger.success(
        "Blurbs written {written:,}, empty {empty:,}, failed {failed:,} (of {selected:,})",
        **summary,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate short blurbs for Jev keepers without full Gemini analysis (#705)."
    )
    p.add_argument(
        "--state",
        action="append",
        default=None,
        help="State code(s), repeatable or comma-separated",
    )
    p.add_argument("--jurisdiction-id", default="")
    p.add_argument("--limit", type=int, default=50, help="Max keepers to blurb (default 50)")
    p.add_argument(
        "--keep-t",
        type=float,
        default=DEFAULT_KEEP_T,
        help=f"Minimum Jev keep-score P(government_meeting)+P(town_hall) (default {DEFAULT_KEEP_T})",
    )
    p.add_argument(
        "--include-analyzed",
        action="store_true",
        help="Also blurb videos that already have policy_analysis_at (default: skip them)",
    )
    p.add_argument(
        "--model",
        default="",
        help="Chat model (default gemini-2.5-flash-lite; deepseek-* routes to DeepSeek)",
    )
    p.add_argument(
        "--max-transcript-chars",
        type=int,
        default=DEFAULT_MAX_TRANSCRIPT_CHARS,
    )
    p.add_argument("--database-url", default="")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    args = build_parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
