"""Analyze the *unanalyzed* meeting transcripts that match a keyword.

The backlog driver (:mod:`llm.gemini.analyze_backlog`) scopes work by jurisdiction /
state / shard — it cannot target "every meeting that mentions fluoride" because those
meetings are scattered across hundreds of jurisdictions. This driver fills that gap: it

  1. resolves a *content* work-list straight from the warehouse — the distinct
     ``video_id``s whose transcript text (``public.event_documents.content_tsv``) matches
     a full-text ``keyword`` query **and** that are still unanalyzed
     (``bronze.bronze_event_youtube.policy_analysis_at IS NULL``), carrying each row's
     resolved ``jurisdiction_id`` / ``state_code`` so the per-video analysis lands in the
     right cache path; then
  2. feeds each video through the *exact same* in-process analysis pipeline the backlog
     uses (``meeting_transcript_policy.run_pipeline`` via
     ``analyze_backlog.build_pipeline_namespace``), driven by the same battle-tested
     :class:`~llm.gemini.analyze_backlog.ModelCycler` so a daily-quota wall rotates models
     / waits for the Pacific reset instead of dying.

Model order leads with ``gemini-2.5-flash-lite`` and escalates to ``gemini-2.5-flash``
only on failure (the project's standing flash-lite-first preference) — the reverse of the
backlog default.

Run (billed — makes Gemini API calls):

    python -m llm.gemini.analyze_keyword --keyword fluoride            # the real run
    python -m llm.gemini.analyze_keyword --keyword fluoride --dry-run  # plan only, no spend
    python -m llm.gemini.analyze_keyword --keyword fluoride --limit 20 # cap the batch

Videos whose ``jurisdiction_id`` does not resolve (empty in bronze) are skipped and
reported — routing them through the default jurisdiction would mislocate the analysis.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from loguru import logger

from llm.gemini.analyze_backlog import (
    DEFAULT_OVERLOAD_COOLDOWN_SECONDS,
    AllModelsExhausted,
    JurisdictionPlan,
    ModelCycler,
    _handle_all_unavailable,
    _model_unavailable_giveup_type,
    _overload_giveup_type,
    _quota_giveup_type,
    _resolve_database_url,
    build_pipeline_namespace,
    format_eta,
    parse_models,
    run_jurisdiction,
)

# Flash-lite first, escalate to flash only on failure (project standing preference;
# reverse of analyze_backlog.DEFAULT_MODELS).
DEFAULT_MODELS: Tuple[str, ...] = (
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)

# Distinct unanalyzed video_ids whose transcript text matches the keyword, with the
# resolved jurisdiction so the per-video pipeline lands in the right cache path.
# Schemas are fully qualified so the connection search_path is irrelevant.
_WORKLIST_SQL = """
    WITH matched AS (
        SELECT DISTINCT video_id
        FROM public.event_documents
        WHERE content_tsv @@ plainto_tsquery('english', %s)
          AND video_id IS NOT NULL
    )
    SELECT y.video_id,
           y.jurisdiction_id,
           COALESCE(y.state_code, '')        AS state_code,
           COALESCE(y.jurisdiction_name, '') AS jurisdiction_name
    FROM matched m
    JOIN bronze.bronze_event_youtube y USING (video_id)
    WHERE y.policy_analysis_at IS NULL
    ORDER BY y.jurisdiction_id, y.video_id
"""


@dataclass(frozen=True)
class KeywordVideo:
    """One unanalyzed transcript matching the keyword, with routing context."""

    video_id: str
    jurisdiction_id: str
    state_code: str
    jurisdiction_name: str


def fetch_keyword_worklist(
    database_url: str, keyword: str, *, limit: Optional[int] = None
) -> Tuple[List[KeywordVideo], int]:
    """Resolve the keyword work-list.

    Returns ``(routable_videos, skipped_no_jurisdiction)``: videos with a non-empty
    ``jurisdiction_id`` (ready to analyze) and a count of matches dropped because bronze
    has no jurisdiction for them (un-routable — would mislocate the cache path).
    """
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_WORKLIST_SQL, (keyword,))
            rows = cur.fetchall()
    finally:
        conn.close()

    routable: List[KeywordVideo] = []
    skipped = 0
    for video_id, jurisdiction_id, state_code, jurisdiction_name in rows:
        if not (jurisdiction_id or "").strip():
            skipped += 1
            continue
        routable.append(
            KeywordVideo(
                video_id=video_id,
                jurisdiction_id=jurisdiction_id.strip(),
                state_code=(state_code or "").strip(),
                jurisdiction_name=(jurisdiction_name or "").strip(),
            )
        )
    if limit is not None and limit > 0:
        routable = routable[:limit]
    return routable, skipped


def _namespace_for(
    video: KeywordVideo,
    *,
    model: str,
    database_url: str,
    prompt_file: str,
) -> argparse.Namespace:
    """A fully-populated single-video analysis Namespace.

    Reuses ``analyze_backlog.build_pipeline_namespace`` (which derives every default and
    sets the backlog knobs: from_bronze / use_local_transcript / skip_analyzed /
    persist_bronze / only_has_transcript / ensure_local_from_bronze / stop_on_quota), then
    pins it to a single ``video_id`` so ``fetch_videos`` returns just this meeting.
    """
    plan = JurisdictionPlan(
        jurisdiction_id=video.jurisdiction_id,
        state_code=video.state_code,
        pending=1,
        newest_pending=None,
    )
    ns = build_pipeline_namespace(
        plan,
        model=model,
        database_url=database_url,
        limit=1,
        prompt_file=prompt_file,
    )
    ns.video_id = video.video_id
    return ns


def run_keyword(args: argparse.Namespace) -> None:
    database_url = _resolve_database_url(getattr(args, "database_url", None))
    keyword = (args.keyword or "").strip()
    if not keyword:
        raise SystemExit("--keyword is required")

    videos, skipped = fetch_keyword_worklist(
        database_url, keyword, limit=getattr(args, "limit", None)
    )
    logger.info(
        "Keyword '{}': {} unanalyzed routable transcript(s); {} skipped (no jurisdiction)",
        keyword,
        len(videos),
        skipped,
    )
    if not videos:
        logger.success("Nothing to do — every '{}' transcript is already analyzed.", keyword)
        return

    if getattr(args, "dry_run", False):
        for i, v in enumerate(videos, 1):
            print(
                f"{i:3}. {v.video_id}  {v.jurisdiction_id} ({v.state_code or '?'})  "
                f"{v.jurisdiction_name}"
            )
        print(
            f"\n{len(videos)} video(s) would be analyzed"
            f"{f' (+{skipped} skipped, no jurisdiction)' if skipped else ''}. "
            "No API calls made (--dry-run)."
        )
        return

    # Only override the flash-lite-first default when --models is explicitly given;
    # parse_models(None) would otherwise return analyze_backlog's flash-FIRST default.
    spec = getattr(args, "models", None)
    models = parse_models(spec) if (spec and spec.strip()) else list(DEFAULT_MODELS)
    cycler = ModelCycler(models=models)
    cooldown_seconds = float(
        getattr(args, "overload_cooldown_seconds", None) or DEFAULT_OVERLOAD_COOLDOWN_SECONDS
    )
    prompt_file = getattr(args, "prompt_file", "") or ""

    quota_giveup = _quota_giveup_type()
    overload_giveup = _overload_giveup_type()
    unavailable_giveup = _model_unavailable_giveup_type()

    total = len(videos)
    done = 0
    analyzed = 0
    failed: List[str] = []

    for video in videos:
        # Retry the SAME video across models on a wall/overload/retired-model give-up.
        while True:
            live_model = cycler.current_or_none(now=time.time())
            if live_model is None:
                if not _handle_all_unavailable(args, cycler):
                    logger.warning("All models exhausted and --on-exhaust=exit — stopping.")
                    _summarize(analyzed, failed, total, skipped)
                    return
                continue

            ns = _namespace_for(
                video,
                model=live_model,
                database_url=database_url,
                prompt_file=prompt_file,
            )
            model = ns.model
            logger.info(
                "[{}/{}] {} — {} ({}) model={}",
                done + 1,
                total,
                video.video_id,
                video.jurisdiction_id,
                video.state_code or "?",
                model,
            )
            try:
                run_jurisdiction(ns)
            except unavailable_giveup as exc:
                logger.warning("Model {} unavailable (retired) — dropping: {}", model, exc)
                cycler.mark_exhausted(model)
                try:
                    cycler.advance(now=time.time())
                except AllModelsExhausted:
                    pass
                continue
            except quota_giveup as exc:
                logger.warning("Model {} hit the daily quota wall: {}", model, exc)
                cycler.mark_exhausted(model)
                continue
            except overload_giveup as exc:
                logger.warning(
                    "Model {} server-overloaded — cooling down {} and rotating: {}",
                    model,
                    format_eta(cooldown_seconds),
                    exc,
                )
                cycler.mark_overloaded(
                    model, now=time.time(), cooldown_seconds=cooldown_seconds
                )
                continue
            except SystemExit as exc:
                # run_pipeline raises SystemExit("No bronze videos…") when this video was
                # analyzed since the work-list was built, or its transcript row vanished.
                logger.info("{}: {}", video.video_id, exc)
                break
            except Exception as exc:  # noqa: BLE001 — one bad video must not kill the batch
                logger.error("Failed {} ({}): {}", video.video_id, video.jurisdiction_id, exc)
                failed.append(video.video_id)
                break
            else:
                analyzed += 1
                break
        done += 1

    _summarize(analyzed, failed, total, skipped)


def _summarize(analyzed: int, failed: Sequence[str], total: int, skipped: int) -> None:
    logger.success(
        "Done: {}/{} analyzed, {} failed, {} skipped (no jurisdiction).",
        analyzed,
        total,
        len(failed),
        skipped,
    )
    if failed:
        logger.warning("Failed video_ids: {}", ", ".join(failed))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keyword",
        required=True,
        help="Full-text query matched against transcript text "
        "(public.event_documents.content_tsv), e.g. 'fluoride'.",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated model rotation, cheapest first "
        f"(default: {','.join(DEFAULT_MODELS)}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Analyze at most N matching videos (default: all).",
    )
    parser.add_argument(
        "--prompt-file",
        default="",
        help="Part-1 prompt passed through to run_pipeline "
        "(default: pipeline default; use prompts/policy_analysis_lite.md for the cheap pass).",
    )
    parser.add_argument(
        "--on-exhaust",
        choices=("wait", "exit"),
        default="wait",
        help="When every model is daily-quota exhausted: wait for the Pacific reset "
        "(default) or exit cleanly.",
    )
    parser.add_argument(
        "--overload-cooldown-seconds",
        type=float,
        default=DEFAULT_OVERLOAD_COOLDOWN_SECONDS,
        help="Seconds to step a model off the rotation after a sustained server-overload "
        f"give-up (502/503/504). Default: {int(DEFAULT_OVERLOAD_COOLDOWN_SECONDS)}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the videos that would be analyzed and exit (NO API calls).",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Warehouse DSN (default: OPEN_NAVIGATOR_DATABASE_URL / pipeline default).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_keyword(args)


if __name__ == "__main__":
    main()
