#!/usr/bin/env python3
"""
Backfill competing-view attribution for a JURISDICTION, reprocessing ONLY the
meetings that are missing it.

The decision page shows the named people behind each side ("Argued by", from
``competing_views[].held_by``) and — going forward — the organizations behind each
side ("Backed by", from ``competing_views[].held_by_organizations``). Analyses run
before those fields were added to the prompt leave them absent, so the row stays
empty. This tool finds exactly those stale meetings in a jurisdiction and re-runs
the *current* prompt on each, so attribution fills in — without touching meetings
that already have it (no wasted spend, no needless rewrites).

"Missing" = the chosen field's KEY is ABSENT from a meeting's decisions (an older
analysis that predates the field) — NOT merely an empty array, which is a current
analysis that genuinely found no identifiable party.

Pipeline (idempotent, mirrors ``reanalyze_decision`` but batched):

  1. For each missing video: re-analyze (Part 1) with ``skip_promote`` /
     ``skip_dbt`` — writes the disk analysis cache only.
  2. ONCE at the end: promote the videos to ``public.civic_event``, load the cached
     analyses into ``bronze.bronze_events_analysis_ai``, then ``dbt run --select
     bronze_decisions_from_ai+`` to rebuild ``public.event_decision``.

Because step 1 runs the current prompt, a ``held_by`` backfill ALSO fills
``held_by_organizations`` for the same meetings (both live in the same Part 1 JSON).

Usage::

    # See the work list (no API calls / no writes) — START HERE.
    python -m llm.gemini.backfill_held_by --jurisdiction-name Tuscaloosa --state AL --dry-run

    # Reprocess every Tuscaloosa meeting missing `held_by` (BILLED Gemini calls).
    python -m llm.gemini.backfill_held_by --jurisdiction-name Tuscaloosa --state AL

    # Target meetings missing the organizations field instead (much larger set —
    # every analysis predating held_by_organizations qualifies).
    python -m llm.gemini.backfill_held_by --jurisdiction-name Tuscaloosa --state AL \\
        --missing held_by_organizations

    # Cap the batch (e.g. smoke-test on the 3 newest missing meetings first).
    python -m llm.gemini.backfill_held_by --jurisdiction-name Tuscaloosa --limit 3
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from loguru import logger

from llm.gemini.reanalyze_decision import DEFAULT_MODEL, _run_dbt, reanalyze

# The competing-view attribution fields this tool can backfill. Restricted to a
# known set so the field name can be spliced into SQL safely.
_FIELDS = ("held_by", "held_by_organizations")


def _select_missing_videos(
    database_url: str,
    *,
    field: str,
    jurisdiction_name: Optional[str],
    jurisdiction_id: Optional[str],
    state_code: Optional[str],
    limit: Optional[int],
) -> list[tuple[str, Optional[str]]]:
    """Return (video_id, state_code) for meetings whose decisions lack ``field``.

    A meeting qualifies when ANY of its decisions has no ``"<field>"`` key in
    competing_views — i.e. it predates that field. Newest meeting first so a
    capped run reprocesses the most relevant meetings.
    """
    if field not in _FIELDS:
        raise ValueError(f"field must be one of {_FIELDS}, got {field!r}")

    import psycopg2

    clauses = ["m.video_id IS NOT NULL"]
    params: list[object] = []
    if jurisdiction_id:
        clauses.append("m.jurisdiction_id = %s")
        params.append(jurisdiction_id)
    if jurisdiction_name:
        clauses.append("m.jurisdiction_name ILIKE %s")
        params.append(f"%{jurisdiction_name}%")
    if state_code:
        clauses.append("m.state_code = %s")
        params.append(state_code.upper())
    where = " AND ".join(clauses)

    # The field key is absent from at least one decision's competing_views. The
    # field name is validated against _FIELDS above, so this interpolation is safe.
    sql = f"""
        SELECT m.video_id, MAX(m.state_code) AS state_code,
               MAX(COALESCE(NULLIF(m.event_date,''), NULLIF(m.meeting_date,''))) AS d
        FROM public.event_decision ed
        JOIN public.event_meeting m ON m.c1_event_id = ed.c1_event_id
        WHERE {where}
          AND ed.competing_views IS NOT NULL
          AND NOT (ed.competing_views::text ~ '"{field}"')
        GROUP BY m.video_id
        ORDER BY d DESC NULLS LAST
    """
    if limit:
        sql += "\n        LIMIT %s"
        params.append(int(limit))

    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [(row[0], row[1]) for row in cur.fetchall()]


def _finalize(database_url: str, states: list[str], *, dry_run: bool) -> None:
    """Promote + load the freshly-cached analyses into bronze, then rebuild marts."""
    from llm.gemini.browser_policy_analysis import _REPO_ROOT

    if dry_run:
        logger.info("[dry-run] would promote → load_analysis_cache_to_bronze → dbt")
        _run_dbt(_REPO_ROOT, dry_run=True)
        return

    state_list = states or None
    try:
        from ingestion.youtube import promote_to_c1_event

        logger.info("Finalize 1/3 — promoting reprocessed videos to civic_event")
        promote_to_c1_event.run(states=state_list, dry_run=False)
    except Exception as exc:  # noqa: BLE001 — FK may already exist / ingestion absent
        logger.warning("promote_to_c1_event failed ({}); continuing to load step.", exc)

    logger.info("Finalize 2/3 — loading analysis cache into bronze_events_analysis_ai")
    from llm.enrichment import load_analysis_cache_to_bronze

    load_analysis_cache_to_bronze.run(
        database_url=database_url, states=state_list, dry_run=False
    )

    logger.info("Finalize 3/3 — rebuilding event_decision via dbt")
    _run_dbt(_REPO_ROOT, dry_run=False)


def backfill(
    *,
    field: str = "held_by",
    jurisdiction_name: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    state_code: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    database_url: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> int:
    """Reprocess a jurisdiction's meetings missing ``field``. Returns an exit code."""
    from llm.gemini.browser_policy_analysis import _database_url

    db_url = _database_url(database_url or None)
    videos = _select_missing_videos(
        db_url,
        field=field,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        limit=limit,
    )

    if not videos:
        logger.success(
            "Nothing to do — every matching meeting already has `{}`.", field
        )
        return 0

    scope = jurisdiction_name or jurisdiction_id or "(all)"
    logger.info(
        "{} meeting(s) in {} missing `{}` to reprocess:", len(videos), scope, field
    )
    for vid, st in videos:
        logger.info("  • {} ({})", vid, st or "?")

    if dry_run:
        logger.info("[dry-run] no API calls / no writes. Re-run without --dry-run to reprocess.")
        _finalize(db_url, [], dry_run=True)
        return 0

    states: set[str] = set()
    failures: list[str] = []
    for i, (vid, st) in enumerate(videos, start=1):
        if st:
            states.add(st.upper())
        logger.info("[{}/{}] re-analyzing {} (model {})", i, len(videos), vid, model)
        try:
            # Analysis only here; promote/load/dbt run ONCE in _finalize.
            rc = reanalyze(
                video_id=vid,
                model=model,
                database_url=db_url,
                skip_promote=True,
                skip_dbt=True,
                dry_run=False,
            )
            if rc != 0:
                failures.append(vid)
        except Exception as exc:  # noqa: BLE001 — one bad video must not abort the batch
            logger.error("Re-analysis failed for {}: {}", vid, exc)
            failures.append(vid)

    logger.info("Analysis pass done ({} ok, {} failed). Loading into bronze + dbt…",
                len(videos) - len(failures), len(failures))
    _finalize(db_url, sorted(states), dry_run=False)

    if failures:
        logger.warning("{} video(s) failed to reprocess: {}", len(failures), ", ".join(failures))
        return 1
    logger.success(
        "Done. Reload the decisions for {} — 'Argued by' (and 'Backed by' for the "
        "organizations) should now be populated where the transcript named the parties.",
        scope,
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--missing",
        choices=_FIELDS,
        default="held_by",
        dest="field",
        help="Which attribution field to backfill (default: held_by). "
             "held_by_organizations targets a much larger set (every analysis "
             "predating that field).",
    )
    parser.add_argument("--jurisdiction-name", default="", help="Match m.jurisdiction_name ILIKE %%name%% (e.g. Tuscaloosa)")
    parser.add_argument("--jurisdiction-id", default="", help="Exact m.jurisdiction_id (alternative to --jurisdiction-name)")
    parser.add_argument("--state", default="", help="2-letter state code filter (e.g. AL)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    parser.add_argument("--database-url", default="", help="Postgres URL (default: NEON_DATABASE_URL_DEV from .env)")
    parser.add_argument("--limit", type=int, default=0, help="Cap the number of meetings reprocessed (0 = all)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the meetings that would be reprocessed; no API calls or writes",
    )
    args = parser.parse_args(argv)

    if not (args.jurisdiction_name or args.jurisdiction_id):
        parser.error("provide --jurisdiction-name or --jurisdiction-id to scope the backfill")

    return backfill(
        field=args.field,
        jurisdiction_name=args.jurisdiction_name.strip() or None,
        jurisdiction_id=args.jurisdiction_id.strip() or None,
        state_code=args.state.strip() or None,
        model=args.model.strip(),
        database_url=args.database_url or None,
        limit=args.limit or None,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
