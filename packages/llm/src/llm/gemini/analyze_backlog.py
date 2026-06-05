#!/usr/bin/env python3
"""
Resumable, quota-aware, model-cycling backlog driver for the meeting-transcript
analysis pipeline.

Drives :func:`llm.gemini.meeting_transcript_policy.run_pipeline` jurisdiction by
jurisdiction, **newest meeting first**, to chew through the ~105k-transcript analysis
backlog on Gemini's free tier:

* **Recent-first work list** — queries the warehouse for jurisdictions that still have
  pending (un-analyzed) transcripts, ordered by their newest pending meeting. Within a
  jurisdiction the pipeline's ``--order-by meeting_date`` keeps newest-first.
* **Model cycling** — runs the current model until the whole key pool is daily-quota
  exhausted (``GenAIDailyQuotaGiveUp``), then advances to the next model and retries the
  *same* jurisdiction (``skip_analyzed`` resumes mid-jurisdiction). When every model is
  exhausted it either sleeps until the next America/Los_Angeles midnight (Gemini free-tier
  daily reset) and clears the exhausted set, or exits — see ``--on-exhaust``.
* **Resumable** — pending work is re-derived from the DB each pass; nothing is persisted
  client-side beyond the analysis JSON the pipeline already writes.

Run the real backfill::

    python -m llm.gemini.analyze_backlog

Preview the plan (no API calls)::

    python -m llm.gemini.analyze_backlog --dry-run

The pure logic (model-cycling state machine + recency SQL / plan construction) lives in
small testable helpers; the wall clock and DB live at the module edge.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from loguru import logger

# Gemini free-tier daily quota resets at midnight Pacific.
PACIFIC = ZoneInfo("America/Los_Angeles")

# Default model rotation: cheapest / highest-free-quota first. flash-lite models have the
# largest free RPD; 2.5-flash is the fallback once both lites are walled. Names confirmed
# against ``default_flash_lite_model`` ("gemini-2.5-flash-lite").
DEFAULT_MODELS: Tuple[str, ...] = (
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
)


# --------------------------------------------------------------------------- #
# Pure data + state machine (unit-tested; no clock, no DB, no network)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class JurisdictionPlan:
    """One jurisdiction with pending transcripts, plus recency metadata."""

    jurisdiction_id: str
    state_code: str
    pending: int
    newest_pending: Optional[datetime]


class AllModelsExhausted(RuntimeError):
    """Raised by :meth:`ModelCycler.advance` when every model is exhausted-for-today."""


@dataclass
class ModelCycler:
    """Ordered model rotation with a per-day exhausted set.

    State machine (pure — the caller owns the clock/reset trigger):

    * :attr:`current` — the model to use right now (first non-exhausted in order).
    * :meth:`mark_exhausted` — flag the current model as daily-quota walled.
    * :meth:`advance` — move to the next non-exhausted model; raises
      :class:`AllModelsExhausted` when none remain.
    * :meth:`reset` — clear the exhausted set (call after the Pacific daily reset).
    """

    models: List[str]
    exhausted: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.models:
            raise ValueError("ModelCycler needs at least one model")
        # De-dupe preserving order.
        seen: set[str] = set()
        deduped: List[str] = []
        for m in self.models:
            m = (m or "").strip()
            if m and m not in seen:
                seen.add(m)
                deduped.append(m)
        if not deduped:
            raise ValueError("ModelCycler needs at least one non-empty model")
        self.models = deduped

    @property
    def all_exhausted(self) -> bool:
        return all(m in self.exhausted for m in self.models)

    @property
    def current(self) -> str:
        for m in self.models:
            if m not in self.exhausted:
                return m
        raise AllModelsExhausted("every model is exhausted-for-today")

    def mark_exhausted(self, model: Optional[str] = None) -> None:
        target = (model or self.current_or_none() or "").strip()
        if target:
            self.exhausted.add(target)

    def current_or_none(self) -> Optional[str]:
        for m in self.models:
            if m not in self.exhausted:
                return m
        return None

    def advance(self) -> str:
        """Move past the current (now-exhausted) model to the next live one."""
        nxt = self.current_or_none()
        if nxt is None:
            raise AllModelsExhausted("every model is exhausted-for-today")
        return nxt

    def reset(self) -> None:
        self.exhausted.clear()


def parse_models(spec: Optional[str]) -> List[str]:
    """Parse a ``--models a,b,c`` spec into an ordered, de-duplicated list."""
    if not spec:
        return list(DEFAULT_MODELS)
    out: List[str] = []
    seen: set[str] = set()
    for raw in spec.split(","):
        m = raw.strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out or list(DEFAULT_MODELS)


def next_pacific_midnight(now: datetime) -> datetime:
    """The next America/Los_Angeles midnight at or after ``now`` (exclusive of now).

    ``now`` may be naive (assumed Pacific) or aware (converted to Pacific). Returned value
    is timezone-aware in Pacific. Pure — the caller passes the clock in.
    """
    if now.tzinfo is None:
        local = now.replace(tzinfo=PACIFIC)
    else:
        local = now.astimezone(PACIFIC)
    tomorrow = (local + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=PACIFIC)


def seconds_until_pacific_midnight(now: datetime) -> float:
    """Non-negative seconds from ``now`` to the next Pacific midnight."""
    target = next_pacific_midnight(now)
    base = now if now.tzinfo is not None else now.replace(tzinfo=PACIFIC)
    return max(0.0, (target - base).total_seconds())


# Recency work-list SQL. event_youtube_with_jurisdiction is the jurisdiction-resolved
# serving view; join transcript (has_transcript) and the analysis table (un-analyzed =
# no successful row). LEAST(...,now()) guards junk future-dated rows from leading.
PENDING_BY_JURISDICTION_SQL = """
    SELECT
        v.jurisdiction_id,
        MAX(COALESCE(v.state_code, '')) AS state_code,
        COUNT(*) AS pending,
        MAX(
            LEAST(
                COALESCE(v.event_date::timestamp, v.published_at),
                now()
            )
        ) AS newest_pending
    FROM public.event_youtube_with_jurisdiction v
    JOIN bronze.bronze_event_youtube_transcript t
        ON t.video_id = v.video_id
       AND t.has_transcript IS TRUE
       AND COALESCE(t.transcript_source, '') NOT LIKE 'excluded:%%'
    WHERE v.policy_analysis_at IS NULL
      AND COALESCE(v.jurisdiction_id, '') <> ''
      AND v.video_url IS NOT NULL
      AND BTRIM(v.video_url) <> ''
    GROUP BY v.jurisdiction_id
    ORDER BY newest_pending DESC NULLS LAST
"""
# NOTE: "pending" = no ``policy_analysis_at`` stamp on bronze_event_youtube. The
# text/policy pipeline (llm.gemini.meeting_transcript_policy) marks a video done by
# stamping ``policy_analysis_at`` (and writing the disk analysis), NOT by inserting
# into ``bronze_events_analysis_ai`` — that table belongs to the separate multimodal
# pipeline. Counting against it made the backlog never tick down. ``policy_analysis_at``
# is the signal this pipeline actually sets and the one that surfaces in the view.


def rows_to_plans(rows: Iterable[Sequence]) -> List[JurisdictionPlan]:
    """Build the recency-ordered jurisdiction plan from DB rows.

    Each row is ``(jurisdiction_id, state_code, pending, newest_pending)`` — the exact
    column order of :data:`PENDING_BY_JURISDICTION_SQL`. Pure: feed it fake rows in tests.
    Rows already arrive recency-ordered from SQL; we keep that order.
    """
    plans: List[JurisdictionPlan] = []
    for r in rows:
        jid = str(r[0] or "").strip()
        if not jid:
            continue
        state = str(r[1] or "").strip().upper()
        pending = int(r[2] or 0)
        if pending <= 0:
            continue
        newest = r[3]
        if newest is not None and not isinstance(newest, datetime):
            newest = None
        plans.append(
            JurisdictionPlan(
                jurisdiction_id=jid,
                state_code=state,
                pending=pending,
                newest_pending=newest,
            )
        )
    return plans


def format_eta(seconds: float) -> str:
    """Human-friendly ``HhMmSs`` ETA string for logging."""
    if seconds < 0 or seconds != seconds:  # negative or NaN
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


# --------------------------------------------------------------------------- #
# Module edge: DB + clock + the pipeline call
# --------------------------------------------------------------------------- #
def _resolve_database_url(explicit: Optional[str]) -> str:
    """Warehouse DSN: explicit flag > OPEN_NAVIGATOR_DATABASE_URL > pipeline default."""
    import os

    from dotenv import load_dotenv

    from llm.gemini.browser_policy_analysis import _REPO_ROOT, _database_url

    if explicit and explicit.strip():
        return explicit.strip()
    load_dotenv(_REPO_ROOT / ".env")
    env = (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
    if env:
        return env
    return _database_url(None)


def fetch_pending_plans(database_url: str) -> List[JurisdictionPlan]:
    """Run the recency work-list query and build the jurisdiction plan."""
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(PENDING_BY_JURISDICTION_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()
    return rows_to_plans(rows)


def build_pipeline_namespace(
    plan: JurisdictionPlan,
    *,
    model: str,
    database_url: str,
    limit: Optional[int],
) -> argparse.Namespace:
    """Mirror the working CLI invocation as a fully-populated Namespace.

    Derives every default from ``meeting_transcript_policy.build_parser`` so nothing
    ``run_pipeline`` reads is missing, then overrides the backlog-driver knobs.
    """
    from llm.gemini.meeting_transcript_policy import build_parser

    ns = build_parser().parse_args([])
    ns.from_bronze = True
    ns.use_local_transcript = True
    ns.skip_analyzed = True
    ns.persist_bronze = True
    ns.order_by = "meeting_date"
    ns.only_has_transcript = True
    ns.stop_on_quota = True
    ns.ensure_local_from_bronze = True
    ns.model = model
    ns.jurisdiction_id = plan.jurisdiction_id
    ns.state = plan.state_code or "AL"
    ns.database_url = database_url
    ns.limit = limit
    return ns


def run_jurisdiction(ns: argparse.Namespace) -> None:
    """Call the analyze pipeline in-process for one jurisdiction."""
    from llm.gemini.meeting_transcript_policy import run_pipeline

    run_pipeline(ns)


def _log_plan(plans: Sequence[JurisdictionPlan], total_pending: int) -> None:
    logger.info("Backlog plan: {} jurisdiction(s), {:,} pending transcript(s)", len(plans), total_pending)
    head = plans[:10]
    for i, p in enumerate(head, 1):
        when = p.newest_pending.date().isoformat() if p.newest_pending else "?"
        logger.info(
            "  {:2}. {:<24} {:<3} pending={:<6,} newest={}",
            i,
            p.jurisdiction_id,
            p.state_code or "?",
            p.pending,
            when,
        )
    if len(plans) > len(head):
        logger.info("  … and {} more jurisdiction(s)", len(plans) - len(head))


def run_backlog(args: argparse.Namespace) -> None:
    database_url = _resolve_database_url(getattr(args, "database_url", None))
    models = parse_models(getattr(args, "models", None))
    cycler = ModelCycler(models=models)

    plans = fetch_pending_plans(database_url)
    total_pending = sum(p.pending for p in plans)
    if args.max_jurisdictions is not None:
        plans = plans[: int(args.max_jurisdictions)]

    _log_plan(plans, total_pending)
    logger.info("Model rotation: {}", " -> ".join(models))

    if args.dry_run:
        logger.success("Dry-run complete — no API calls made.")
        return

    if not plans:
        logger.success("Nothing pending — backlog is clear.")
        return

    start = time.monotonic()
    done = 0
    total_j = len(plans)
    for plan in plans:
        # Retry the same jurisdiction across models until it completes or all models wall.
        while True:
            try:
                ns = build_pipeline_namespace(
                    plan,
                    model=cycler.current,
                    database_url=database_url,
                    limit=args.limit_per_jurisdiction,
                )
            except AllModelsExhausted:
                if not _handle_all_exhausted(args, cycler):
                    logger.success("Exiting on quota exhaustion (--on-exhaust exit).")
                    return
                continue
            model = ns.model
            logger.info(
                "[{}/{}] {} ({}) — pending~{:,}, model={}",
                done + 1,
                total_j,
                plan.jurisdiction_id,
                plan.state_code or "?",
                plan.pending,
                model,
            )
            try:
                run_jurisdiction(ns)
            except _quota_giveup_type() as exc:
                logger.warning(
                    "Model {} hit the daily quota wall on {}: {}",
                    model,
                    plan.jurisdiction_id,
                    exc,
                )
                cycler.mark_exhausted(model)
                try:
                    cycler.advance()
                except AllModelsExhausted:
                    if not _handle_all_exhausted(args, cycler):
                        logger.success("Exiting on quota exhaustion (--on-exhaust exit).")
                        return
                # Loop again: retry same jurisdiction on the next (or reset) model.
                continue
            except SystemExit as exc:
                # run_pipeline raises SystemExit("No bronze videos…") when a jurisdiction
                # has nothing left (e.g. all analyzed since the plan was built). Treat as
                # done-for-this-jurisdiction, not fatal.
                logger.info("{}: {}", plan.jurisdiction_id, exc)
                break
            else:
                break
        done += 1
        elapsed = time.monotonic() - start
        rate = done / elapsed if elapsed > 0 else 0.0
        remaining = total_j - done
        eta = remaining / rate if rate > 0 else float("nan")
        logger.info(
            "Progress {}/{} jurisdictions ({:.2f}/min, ETA {})",
            done,
            total_j,
            rate * 60.0,
            format_eta(eta),
        )

    logger.success("Backlog driver finished: {}/{} jurisdictions processed.", done, total_j)


def _quota_giveup_type():
    from llm.gemini.genai_text_client import GenAIDailyQuotaGiveUp

    return GenAIDailyQuotaGiveUp


def _handle_all_exhausted(args: argparse.Namespace, cycler: ModelCycler) -> bool:
    """All models walled. Return True to keep going (waited+reset), False to exit."""
    if args.on_exhaust == "exit":
        return False
    now = datetime.now(timezone.utc)
    wait_s = seconds_until_pacific_midnight(now)
    wake = next_pacific_midnight(now)
    logger.warning(
        "All models exhausted for today. Sleeping {} until Pacific reset ({}).",
        format_eta(wait_s),
        wake.isoformat(),
    )
    # +30s slack so we wake just past midnight Pacific.
    time.sleep(wait_s + 30.0)
    cycler.reset()
    logger.info("Pacific daily reset reached — model rotation cleared, resuming.")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated model rotation, cheapest first "
        f"(default: {','.join(DEFAULT_MODELS)})",
    )
    parser.add_argument(
        "--limit-per-jurisdiction",
        type=int,
        default=None,
        help="Max videos per jurisdiction per pass (passthrough to args.limit; default: all)",
    )
    parser.add_argument(
        "--max-jurisdictions",
        type=int,
        default=None,
        help="Process at most N jurisdictions (testing cap; default: all)",
    )
    parser.add_argument(
        "--on-exhaust",
        choices=("wait", "exit"),
        default="wait",
        help="When every model is daily-quota exhausted: wait for the Pacific reset "
        "(default) or exit cleanly",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the recency-ordered jurisdiction plan with pending counts and exit "
        "(NO API calls)",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Warehouse DSN (default: OPEN_NAVIGATOR_DATABASE_URL / NEON_DATABASE_URL_DEV)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_backlog(args)


if __name__ == "__main__":
    main()
