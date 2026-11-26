"""Screen YouTube catalog metadata with Jev before caption download.

Uses the same meeting-kind labels (including ``town_hall``) and Noul questions as
``screen_transcripts``, but the state is title + description (+ optional channel
title) from ``bronze.bronze_event_youtube``. Results land in
``bronze.bronze_video_meta_screen_jev`` so transcript screens are never overwritten.

Compare against transcript screens with ``--compare`` (AL sample CSV). Caption
backfill is not gated here — see ``jev-meta-and-scale-design.md``.

Usage::

    python -m llm.typesafe.screen_video_meta --state AL --limit 300 --dry-run
    python -m llm.typesafe.screen_video_meta --state AL --limit 300
    python -m llm.typesafe.screen_video_meta --compare --state AL --limit 300
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from loguru import logger

from llm.typesafe.client import JevClient, JevError, choice, noul
from llm.typesafe.keep_decision import (
    DEFAULT_KEEP_THRESHOLD,
    decide_row,
    write_review_csv,
)
from llm.typesafe.screen_transcripts import (
    MEETING_KEEP_KIND_KEYS,
    MEETING_KINDS,
    TABLE as TRANSCRIPT_SCREEN_TABLE,
    QUESTION_VERSION as TRANSCRIPT_QUESTION_VERSION,
    meeting_keep_p,
    meeting_keep_p_below,
)
from llm.usage.calls import llm_call_context

TABLE = "bronze.bronze_video_meta_screen_jev"

# Same criteria as the transcript screen; wording refers to title/description.
META_QUESTIONS: dict[str, dict[str, Any]] = {
    "meeting_kind": choice(
        "What kind of video this title and description describe", MEETING_KINDS
    ),
    "has_decisions": noul(
        "The title or description indicates the body votes on, approves, adopts, denies "
        "or tables a motion, ordinance, resolution, contract, budget item, rezoning or "
        "appointment"
    ),
    "mentions_data_center": noul(
        "The title or description mentions a data center: a proposed, approved or "
        "operating facility, its zoning, tax deal, power or water use, or residents' "
        "views on one"
    ),
}

QUESTION_VERSION = hashlib.sha256(
    json.dumps(META_QUESTIONS, sort_keys=True).encode()
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
    state_chars                 integer NOT NULL,
    input_tokens                integer,
    answers                     jsonb NOT NULL,
    screened_at                 timestamptz NOT NULL DEFAULT now()
)
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE} (
    video_id, question_version, model, meeting_kind, meeting_kind_probabilities,
    has_decisions_p, mentions_data_center_p, state_chars, input_tokens, answers,
    screened_at
) VALUES (
    %(video_id)s, %(question_version)s, %(model)s, %(meeting_kind)s,
    %(meeting_kind_probabilities)s, %(has_decisions_p)s, %(mentions_data_center_p)s,
    %(state_chars)s, %(input_tokens)s, %(answers)s, %(screened_at)s
)
ON CONFLICT (video_id) DO UPDATE SET
    question_version = EXCLUDED.question_version,
    model = EXCLUDED.model,
    meeting_kind = EXCLUDED.meeting_kind,
    meeting_kind_probabilities = EXCLUDED.meeting_kind_probabilities,
    has_decisions_p = EXCLUDED.has_decisions_p,
    mentions_data_center_p = EXCLUDED.mentions_data_center_p,
    state_chars = EXCLUDED.state_chars,
    input_tokens = EXCLUDED.input_tokens,
    answers = EXCLUDED.answers,
    screened_at = EXCLUDED.screened_at
"""

DEFAULT_COMPARE_CSV = Path(
    "data/cache/jev_meta_vs_transcript_al_review.csv"
)
DEFAULT_REVIEW_CSV = Path(
    "data/cache/jev_meta_vs_transcript_al_final_review.csv"
)


def build_meta_state(
    *,
    title: str | None,
    description: str | None,
    channel_title: str | None = None,
) -> str:
    """Compact text Jev reads instead of a transcript."""
    parts: list[str] = []
    if channel_title and str(channel_title).strip():
        parts.append(f"Channel: {str(channel_title).strip()}")
    if title and str(title).strip():
        parts.append(f"Title: {str(title).strip()}")
    if description and str(description).strip():
        parts.append(f"Description: {str(description).strip()}")
    return "\n\n".join(parts).strip()


@dataclass
class MetaScreenResult:
    video_id: str
    model: str
    meeting_kind: str | None
    meeting_kind_probabilities: dict[str, float]
    has_decisions_p: float | None
    mentions_data_center_p: float | None
    state_chars: int
    input_tokens: int | None
    answers: dict[str, Any]

    def row(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "question_version": QUESTION_VERSION,
            "model": self.model,
            "meeting_kind": self.meeting_kind,
            "meeting_kind_probabilities": json.dumps(self.meeting_kind_probabilities),
            "has_decisions_p": self.has_decisions_p,
            "mentions_data_center_p": self.mentions_data_center_p,
            "state_chars": self.state_chars,
            "input_tokens": self.input_tokens,
            "answers": json.dumps(self.answers),
            "screened_at": datetime.now(UTC),
        }


def screen_meta(
    client: JevClient,
    video_id: str,
    state: str,
) -> MetaScreenResult | None:
    """Ask Jev about one video's catalog text. ``None`` if title and description are empty."""
    text = (state or "").strip()
    if not text:
        return None
    with llm_call_context(stage="jev_meta_screen", video_id=video_id):
        resp = client.system_one(state=text, questions=META_QUESTIONS)
    kind_ans = resp.answers.get("meeting_kind")
    probs = dict(kind_ans.probabilities) if kind_ans and kind_ans.probabilities else {}
    meeting_kind = max(probs, key=probs.get) if probs else (
        kind_ans.choice if kind_ans else None
    )
    def _noul(name: str) -> float | None:
        a = resp.answers.get(name)
        return a.noul if a is not None else None

    return MetaScreenResult(
        video_id=video_id,
        model=resp.model or client.model,
        meeting_kind=meeting_kind,
        meeting_kind_probabilities={k: float(v) for k, v in probs.items()},
        has_decisions_p=_noul("has_decisions"),
        mentions_data_center_p=_noul("mentions_data_center"),
        state_chars=len(text),
        input_tokens=resp.input_tokens,
        answers=resp.raw.get("answers", {}) if isinstance(resp.raw, dict) else {},
    )


def select_sql(
    *,
    states: Iterable[str],
    jurisdiction_id: str,
    rescreen: bool,
    analyzed_only: bool,
) -> tuple[str, list[Any]]:
    """Catalog rows with title/description, newest published first."""
    where = [
        "(COALESCE(NULLIF(TRIM(e.title), ''), NULLIF(TRIM(e.description), '')) IS NOT NULL)"
    ]
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
    if not rescreen:
        where.append(
            f"NOT EXISTS (SELECT 1 FROM {TABLE} s WHERE s.video_id = e.video_id "
            "AND s.question_version = %s)"
        )
        params.append(QUESTION_VERSION)
    sql = f"""
        SELECT e.video_id, e.title, e.description, e.published_at, e.state_code,
               e.jurisdiction_id, c.channel_title
        FROM bronze.bronze_event_youtube e
        LEFT JOIN bronze.bronze_events_channels c ON c.channel_id = e.channel_id
        WHERE {" AND ".join(where)}
        ORDER BY e.published_at DESC NULLS LAST
        LIMIT %s
    """
    return sql, params


def _database_url(explicit: str) -> str:
    from llm.gemini.analyze_backlog import _resolve_database_url

    return _resolve_database_url(explicit)


def run_screen(args: argparse.Namespace) -> dict[str, Any]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    from llm.usage.prices import load_prices, model_price

    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    sql, params = select_sql(
        states=states,
        jurisdiction_id=args.jurisdiction_id or "",
        rescreen=args.rescreen,
        analyzed_only=bool(args.analyzed_only),
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
        "{:,} catalog video(s) to meta-screen (questions {})",
        len(rows),
        QUESTION_VERSION,
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
            len(
                build_meta_state(
                    title=r.get("title"),
                    description=r.get("description"),
                    channel_title=r.get("channel_title"),
                )
            )
            // 4
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
                state = build_meta_state(
                    title=row.get("title"),
                    description=row.get("description"),
                    channel_title=row.get("channel_title"),
                )
                try:
                    result = screen_meta(client, vid, state)
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
                keep = meeting_keep_p(result.meeting_kind_probabilities)
                logger.info(
                    "[{}/{}] {} {} keep={:.2f} decisions={:.2f} ({} chars)",
                    i,
                    len(rows),
                    vid,
                    result.meeting_kind,
                    keep or 0.0,
                    result.has_decisions_p or 0.0,
                    result.state_chars,
                )
        finally:
            conn.close()
    logger.success(
        "Meta-screened {screened:,}, empty {empty:,}, failed {failed:,}; "
        "{input_tokens:,} input tokens".format(**summary)
    )
    return summary


def run_compare(args: argparse.Namespace) -> dict[str, Any]:
    """Join meta ↔ transcript screens; write a spreadsheet review CSV."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    database_url = _database_url(args.database_url)
    states = [s for part in (args.state or []) for s in part.split(",")]
    state_list = [s.strip().upper() for s in states if s and s.strip()]
    threshold = float(args.threshold)
    out_path = Path(args.output) if args.output else DEFAULT_COMPARE_CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)

    where = [
        "t.question_version = %s",
        "m.question_version = %s",
    ]
    params: list[Any] = [TRANSCRIPT_QUESTION_VERSION, QUESTION_VERSION]
    if state_list:
        where.append("e.state_code = ANY(%s)")
        params.append(state_list)
    if args.analyzed_only:
        where.append("e.policy_analysis_at IS NOT NULL")
    sql = f"""
        SELECT e.video_id, e.title, e.state_code, e.jurisdiction_id,
               t.meeting_kind AS transcript_kind,
               t.meeting_kind_probabilities AS transcript_probs,
               m.meeting_kind AS meta_kind,
               m.meeting_kind_probabilities AS meta_probs
        FROM {TRANSCRIPT_SCREEN_TABLE} t
        JOIN {TABLE} m ON m.video_id = t.video_id
        JOIN bronze.bronze_event_youtube e ON e.video_id = t.video_id
        WHERE {" AND ".join(where)}
        ORDER BY e.published_at DESC NULLS LAST
        LIMIT %s
    """
    params.append(args.limit)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [TABLE])
            if cur.fetchone()[0] is None:
                logger.warning("Meta screen table missing — run a meta screen first.")
                return {"n": 0, "agree": 0, "disagree": 0}
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    out_rows: list[dict[str, Any]] = []
    agree = disagree = 0
    for r in rows:
        t_probs = r["transcript_probs"] or {}
        m_probs = r["meta_probs"] or {}
        if isinstance(t_probs, str):
            t_probs = json.loads(t_probs)
        if isinstance(m_probs, str):
            m_probs = json.loads(m_probs)
        t_keep = meeting_keep_p(t_probs)
        m_keep = meeting_keep_p(m_probs)
        t_gate = "skip" if meeting_keep_p_below(t_keep, threshold) else "keep"
        m_gate = "skip" if meeting_keep_p_below(m_keep, threshold) else "keep"
        same = t_gate == m_gate
        if same:
            agree += 1
        else:
            disagree += 1
        meta_adj, final = decide_row(
            title=r.get("title"),
            transcript_keep=t_keep,
            meta_keep=m_keep,
            threshold=threshold,
        )
        out_rows.append(
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "state_code": r["state_code"],
                "jurisdiction_id": r["jurisdiction_id"],
                "transcript_kind": r["transcript_kind"],
                "meta_kind": r["meta_kind"],
                "transcript_keep_score": t_keep,
                "meta_keep_score": m_keep,
                "meta_keep_score_adj": meta_adj,
                "transcript_gate": t_gate,
                "meta_gate": m_gate,
                "agree_at_threshold": same,
                "final_decision": final,
                "threshold": threshold,
                "youtube_url": f"https://www.youtube.com/watch?v={r['video_id']}",
                "keep_kind_keys": ",".join(MEETING_KEEP_KIND_KEYS),
            }
        )

    return _write_compare_outputs(
        out_rows, out_path, threshold, agree, disagree, DEFAULT_REVIEW_CSV
    )


def reprocess_compare_csv(
    input_path: Path,
    *,
    output_path: Path | None = None,
    review_path: Path | None = None,
    threshold: float = DEFAULT_KEEP_THRESHOLD,
) -> dict[str, Any]:
    """Re-apply title cues + final decision on an existing compare CSV (no DB/Jev)."""
    rows_in = list(csv.DictReader(input_path.open(encoding="utf-8")))
    out_rows: list[dict[str, Any]] = []
    agree = disagree = 0
    for r in rows_in:
        t_keep = _float_or_none(r.get("transcript_keep_score"))
        m_keep = _float_or_none(r.get("meta_keep_score"))
        t_gate = r.get("transcript_gate") or (
            "skip" if meeting_keep_p_below(t_keep, threshold) else "keep"
        )
        m_gate = r.get("meta_gate") or (
            "skip" if meeting_keep_p_below(m_keep, threshold) else "keep"
        )
        same = t_gate == m_gate
        if same:
            agree += 1
        else:
            disagree += 1
        meta_adj, final = decide_row(
            title=r.get("title"),
            transcript_keep=t_keep,
            meta_keep=m_keep,
            threshold=threshold,
        )
        row = dict(r)
        row["meta_keep_score_adj"] = meta_adj
        row["final_decision"] = final
        row["threshold"] = threshold
        row["agree_at_threshold"] = same
        out_rows.append(row)

    out = output_path or input_path
    rev = review_path or DEFAULT_REVIEW_CSV
    return _write_compare_outputs(out_rows, out, threshold, agree, disagree, rev)


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _write_compare_outputs(
    out_rows: list[dict[str, Any]],
    out_path: Path,
    threshold: float,
    agree: int,
    disagree: int,
    review_path: Path,
) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        if out_rows:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        else:
            fh.write("")

    n_review = write_review_csv(out_rows, review_path)

    n = len(out_rows)
    rate = (agree / n) if n else 0.0
    by_final = {"keep": 0, "skip": 0, "review": 0}
    for r in out_rows:
        d = str(r.get("final_decision") or "skip")
        by_final[d] = by_final.get(d, 0) + 1

    logger.success(
        "Compare {:,} video(s): agree={:,} disagree={:,} ({:.1%} agree) at T={:.2f} → {}",
        n,
        agree,
        disagree,
        rate,
        threshold,
        out_path,
    )
    logger.info(
        "Final decisions: keep={keep:,} skip={skip:,} review={review:,} → {}",
        review_path,
        **by_final,
    )
    meta_skip_tx_keep = sum(
        1
        for r in out_rows
        if r.get("meta_gate") == "skip" and r.get("transcript_gate") == "keep"
    )
    meta_keep_tx_skip = sum(
        1
        for r in out_rows
        if r.get("meta_gate") == "keep" and r.get("transcript_gate") == "skip"
    )
    logger.info(
        "Disagreements: meta_skip∩transcript_keep={:,}; meta_keep∩transcript_skip={:,}",
        meta_skip_tx_keep,
        meta_keep_tx_skip,
    )
    return {
        "n": n,
        "agree": agree,
        "disagree": disagree,
        "agree_rate": rate,
        "meta_skip_transcript_keep": meta_skip_tx_keep,
        "meta_keep_transcript_skip": meta_keep_tx_skip,
        "final_keep": by_final.get("keep", 0),
        "final_skip": by_final.get("skip", 0),
        "final_review": by_final.get("review", 0),
        "review_count": n_review,
        "output": str(out_path),
        "review_output": str(review_path),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Screen YouTube title/description with Jev (pre-caption compare)."
    )
    p.add_argument("--state", action="append", default=None)
    p.add_argument("--jurisdiction-id", default="")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--rescreen", action="store_true")
    p.add_argument(
        "--analyzed-only",
        action="store_true",
        help="Only videos with policy_analysis_at (for compare samples)",
    )
    p.add_argument("--model", default="")
    p.add_argument("--database-url", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--compare",
        action="store_true",
        help="Join meta ↔ transcript screens and write a review CSV (no Jev calls)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Keep-score floor for agree/disagree (default 0.6)",
    )
    p.add_argument(
        "--output",
        default="",
        help=f"Compare CSV path (default {DEFAULT_COMPARE_CSV})",
    )
    p.add_argument(
        "--reprocess-csv",
        default="",
        metavar="PATH",
        help="Re-apply title cues + final keep/skip/review on an existing compare CSV",
    )
    p.add_argument(
        "--review-output",
        default="",
        help=f"Review-only CSV path (default {DEFAULT_REVIEW_CSV})",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        if args.reprocess_csv:
            reprocess_compare_csv(
                Path(args.reprocess_csv),
                output_path=Path(args.output) if args.output else None,
                review_path=Path(args.review_output) if args.review_output else None,
                threshold=float(args.threshold),
            )
        elif args.compare:
            run_compare(args)
        else:
            run_screen(args)
    except JevError as exc:
        logger.error("{}", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
