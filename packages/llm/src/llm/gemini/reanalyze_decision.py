#!/usr/bin/env python3
"""
Re-analyze a SINGLE meeting video end-to-end so its decision(s) pick up the
*current* policy prompt — most importantly ``competing_views[].held_by`` (who
argued each side), which older analyses predate and therefore leave empty.

Use this to eyeball speaker attribution on one decision before committing to a
full-jurisdiction backfill (``llm.gemini.analyze_backlog``).

Pipeline (every step is idempotent — safe to re-run):

  1. **Force re-analysis** of the one video
     (``meeting_transcript_policy.run_pipeline`` with ``from_bronze`` + ``video_id``
     and ``skip_analyzed=False``) → writes the disk analysis cache and persists
     to bronze. Reads the transcript already in
     ``bronze.bronze_event_youtube_transcript`` (run the jurisdiction transcript
     backfill first if the video has none).
  2. **Promote** the video to ``public.civic_event``
     (``ingestion.youtube.promote_to_c1_event.run``) so the analysis FK target
     exists.
  3. **Load** the cached analysis JSON into ``bronze.bronze_events_analysis_ai``
     (``llm.enrichment.load_analysis_cache_to_bronze.run``).
  4. **dbt** ``run --select bronze_decisions_from_ai+`` (rebuilds
     ``public.event_decision``) — unless ``--skip-dbt``.

After it finishes, reload the decision page: the "Argued by" row on each
competing-view column fills in from the freshly-extracted ``held_by`` ids.

Usage::

    # Re-analyze one decision's video (Rule 2C example)
    python -m llm.gemini.reanalyze_decision --video-id CMbzuxL6CWc

    # Pick the model explicitly (default is the healthy gemini-2.5-flash)
    python -m llm.gemini.reanalyze_decision --video-id CMbzuxL6CWc --model gemini-2.5-flash

    # See what it would do — lists the video, no API calls / no writes
    python -m llm.gemini.reanalyze_decision --video-id CMbzuxL6CWc --dry-run

    # Analysis only; skip the bronze promote/load and the dbt rebuild
    python -m llm.gemini.reanalyze_decision --video-id CMbzuxL6CWc --skip-promote --skip-dbt
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

# Default analysis model. gemini-2.5-flash is the healthy lead model; flash-lite
# is 504-congested and gemini-2.0-flash-lite is retired (404), so we do NOT
# default to either.
DEFAULT_MODEL = "gemini-2.5-flash"

# dbt selector: the AI-extraction bronze model and everything downstream of it
# (notably public.event_decision, which carries competing_views.held_by).
_DBT_SELECT = "bronze_decisions_from_ai+"


def _resolve_video_geo(database_url: str, video_id: str) -> tuple[str, Optional[str]]:
    """Look up (jurisdiction_id, state_code) for a video from bronze.

    ``run_pipeline`` filters bronze videos by *both* jurisdiction_id and
    video_id, so we need the video's own jurisdiction to target it.
    """
    import psycopg2

    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT jurisdiction_id, state_code, jurisdiction_name
            FROM bronze.bronze_event_youtube
            WHERE video_id = %s
            LIMIT 1
            """,
            (video_id,),
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(
            f"No bronze.bronze_event_youtube row for video_id={video_id!r} — "
            "is the id correct, and has the video been ingested?"
        )
    jurisdiction_id, state_code, jurisdiction_name = row
    logger.info(
        "Target video {} → jurisdiction_id={} state={} ({})",
        video_id,
        jurisdiction_id,
        state_code or "?",
        jurisdiction_name or "?",
    )
    return jurisdiction_id, state_code


def _build_namespace(
    *,
    video_id: str,
    jurisdiction_id: str,
    state_code: Optional[str],
    model: str,
    database_url: str,
    dry_run: bool,
) -> argparse.Namespace:
    """Mirror the working single-video CLI invocation as a populated Namespace.

    Derives every default from ``meeting_transcript_policy.build_parser`` (so
    nothing ``run_pipeline`` reads is missing), then overrides the knobs that
    make this a forced, single-video, bronze-persisting run.
    """
    from llm.gemini.meeting_transcript_policy import build_parser

    ns = build_parser().parse_args([])
    ns.from_bronze = True
    ns.video_id = video_id
    ns.jurisdiction_id = jurisdiction_id
    ns.state = state_code or "AL"
    # The whole point: re-analyze even though this video already has an analysis,
    # so the new prompt's held_by attribution gets written.
    ns.skip_analyzed = False
    ns.use_local_transcript = True
    ns.ensure_local_from_bronze = True
    ns.only_has_transcript = True
    ns.persist_bronze = True
    # held_by lives in the Part 1 structured JSON; the Part 2 markdown report is
    # not needed to eyeball attribution, so skip it (cheaper, faster).
    ns.run_part_2 = False
    ns.order_by = "meeting_date"
    ns.model = model
    ns.database_url = database_url
    ns.limit = 1
    ns.dry_run = dry_run
    return ns


def _run_dbt(repo_root: Path, *, dry_run: bool) -> None:
    cmd = ["dbt", "run", "--select", _DBT_SELECT]
    dbt_dir = repo_root / "dbt_project"
    if dry_run:
        logger.info("[dry-run] would run: (cd {}) {}", dbt_dir, " ".join(cmd))
        return
    if shutil.which("dbt") is None:
        logger.warning(
            "dbt not on PATH — skipping the mart rebuild. Run it yourself:\n"
            "    cd {} && dbt run --select {}",
            dbt_dir,
            _DBT_SELECT,
        )
        return
    logger.info("Rebuilding marts: (cd {}) {}", dbt_dir, " ".join(cmd))
    result = subprocess.run(cmd, cwd=dbt_dir, check=False)
    if result.returncode != 0:
        logger.warning(
            "dbt exited {} — if the decision didn't refresh, retry with "
            "`--full-refresh --select bronze_decisions_from_ai`.",
            result.returncode,
        )


def reanalyze(
    *,
    video_id: str,
    model: str = DEFAULT_MODEL,
    database_url: Optional[str] = None,
    skip_promote: bool = False,
    skip_dbt: bool = False,
    dry_run: bool = False,
) -> int:
    """Run the four-step single-video re-analysis pipeline. Returns an exit code."""
    from llm.gemini.browser_policy_analysis import _REPO_ROOT, _database_url
    from llm.gemini.meeting_transcript_policy import run_pipeline

    db_url = _database_url(database_url or None)
    jurisdiction_id, state_code = _resolve_video_geo(db_url, video_id)

    # ---- 1. force re-analysis of the single video --------------------------
    logger.info("Step 1/4 — analyzing {} with model {}", video_id, model)
    ns = _build_namespace(
        video_id=video_id,
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        model=model,
        database_url=db_url,
        dry_run=dry_run,
    )
    run_pipeline(ns)
    if dry_run:
        logger.success("[dry-run] analysis listing done; skipping promote/load/dbt.")
        _run_dbt(_REPO_ROOT, dry_run=True)
        return 0

    states = (state_code.upper(),) if state_code else None

    if skip_promote:
        logger.info("Steps 2-3 — skipped (--skip-promote)")
    else:
        # ---- 2. ensure the civic_event FK target exists --------------------
        logger.info("Step 2/4 — promoting video to public.civic_event")
        try:
            from ingestion.youtube import promote_to_c1_event

            promote_to_c1_event.run(states=states, dry_run=False)
        except Exception as exc:  # ingestion may be absent / FK already present
            logger.warning(
                "promote_to_c1_event failed ({}). If the load step hits an FK "
                "error, run `python -m ingestion.youtube.promote_to_c1_event "
                "--states {}` manually.",
                exc,
                state_code or "AL",
            )

        # ---- 3. load cached analysis JSON into bronze ----------------------
        logger.info("Step 3/4 — loading analysis cache into bronze_events_analysis_ai")
        from llm.enrichment import load_analysis_cache_to_bronze

        load_analysis_cache_to_bronze.run(
            database_url=db_url,
            states=list(states) if states else None,
            dry_run=False,
        )

    # ---- 4. rebuild the marts ---------------------------------------------
    if skip_dbt:
        logger.info("Step 4/4 — skipped (--skip-dbt). Rebuild with:")
        logger.info("    cd {} && dbt run --select {}", _REPO_ROOT / "dbt_project", _DBT_SELECT)
    else:
        logger.info("Step 4/4 — rebuilding event_decision via dbt")
        _run_dbt(_REPO_ROOT, dry_run=False)

    logger.success(
        "Done. Reload the decision for video {} — competing-view 'Argued by' "
        "should now be populated (if the transcript named who took each side).",
        video_id,
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--video-id", required=True, help="YouTube video id of the meeting to re-analyze")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model (default: {DEFAULT_MODEL} — healthy; avoid flash-lite / 2.0-flash-lite)",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Postgres URL (default: NEON_DATABASE_URL_DEV / NEON_DATABASE_URL from .env)",
    )
    parser.add_argument(
        "--skip-promote",
        action="store_true",
        help="Skip the civic_event promote + bronze load (run analysis only)",
    )
    parser.add_argument(
        "--skip-dbt",
        action="store_true",
        help="Skip the dbt mart rebuild (print the command instead)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the targeted video and the steps; no API calls or writes",
    )
    args = parser.parse_args(argv)
    return reanalyze(
        video_id=args.video_id.strip(),
        model=args.model.strip(),
        database_url=args.database_url or None,
        skip_promote=args.skip_promote,
        skip_dbt=args.skip_dbt,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
