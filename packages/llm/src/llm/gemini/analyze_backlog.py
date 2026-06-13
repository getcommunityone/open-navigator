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
* **Model cycling** — runs the current model until it walls, then advances to the next
  model and retries the *same* jurisdiction (``skip_analyzed`` resumes mid-jurisdiction).
  Two distinct wall types:

  - ``GenAIDailyQuotaGiveUp`` (pool-wide daily quota / 429) — a *daily* wall. When every
    model is daily-walled the driver sleeps until the next America/Los_Angeles midnight
    (Gemini free-tier reset) and clears the exhausted set, or exits — see ``--on-exhaust``.
  - ``GenAIServerOverloadGiveUp`` (sustained 502/503/504 / ``DEADLINE_EXCEEDED``) — a
    *transient* congestion blip. The model goes on a short cooldown (``--overload-cooldown-\
    seconds``, default 600s) and the driver rotates to the next live model immediately.
    When *all* live models are merely cooling down, it short-waits only until the soonest
    cooldown expires — it does NOT wait until Pacific midnight for transient congestion.
* **Resumable** — pending work is re-derived from the DB each pass; nothing is persisted
  client-side beyond the analysis JSON the pipeline already writes.

Run the real backfill, leading with a healthy model::

    python -m llm.gemini.analyze_backlog \
        --models gemini-2.5-flash,gemini-2.5-flash-lite

Restrict to one or more states::

    python -m llm.gemini.analyze_backlog --state GA --state AL
    python -m llm.gemini.analyze_backlog --state GA,AL

Run N disjoint shards across processes (clean multi-process parallelism, no overlap)::

    python -m llm.gemini.analyze_backlog --shard 0/3 &
    python -m llm.gemini.analyze_backlog --shard 1/3 &
    python -m llm.gemini.analyze_backlog --shard 2/3 &

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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from loguru import logger

# Gemini free-tier daily quota resets at midnight Pacific.
PACIFIC = ZoneInfo("America/Los_Angeles")

# Default cooldown applied to a model after a sustained server-overload give-up
# (502/503/504). This is a *temporary* rotation, NOT the daily quota wall: the model
# is congested right now, so we step off it for ~10 min and try the next live model.
DEFAULT_OVERLOAD_COOLDOWN_SECONDS: float = 600.0

# Default model rotation, healthy/fast model FIRST. ``gemini-2.5-flash`` leads because it
# is the reliable, currently-healthy model; ``gemini-2.5-flash-lite`` follows as the
# higher-free-RPD fallback. ``gemini-2.0-flash-lite`` was RETIRED by Google (the API now
# 404s "This model models/gemini-2.0-flash-lite is no longer available"), so it is gone
# from the defaults — a default run that rotated onto it used to crash the shard. If a run
# ever does rotate onto a retired model, the driver now drops it from rotation (see
# GenAIModelUnavailableGiveUp) instead of dying.
DEFAULT_MODELS: Tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
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
    """Ordered model rotation with a per-day exhausted set AND a temporary cooldown map.

    Two distinct "model unavailable" notions, kept separate on purpose:

    * :attr:`exhausted` — a *daily* quota wall (``GenAIDailyQuotaGiveUp``). Cleared only
      by :meth:`reset` after the Pacific midnight quota reset.
    * :attr:`cooldowns` — a *temporary* server-overload step-off (``GenAIServerOverload\
      GiveUp``), model -> epoch-seconds-until-available. Expires on its own clock; a
      driver waits only until the soonest expiry, not until Pacific midnight.

    State machine (pure — the caller owns the clock; ``now`` is passed in, never read
    from a wall clock inside the class):

    * :attr:`current` / :meth:`current_or_none` — first model that is neither daily-walled
      nor (given ``now``) still cooling down.
    * :meth:`mark_exhausted` — flag a model as daily-quota walled.
    * :meth:`mark_overloaded` — put a model on a temporary cooldown.
    * :meth:`advance` — return the next live model; raises :class:`AllModelsExhausted`
      when none are available *right now* (all daily-walled and/or cooling down).
    * :meth:`seconds_until_any_available` — soonest cooldown expiry, or ``None`` when a
      model is available now (or the only blockers are daily walls).
    * :meth:`reset` — clear the daily exhausted set (NOT cooldowns).
    """

    models: List[str]
    exhausted: set[str] = field(default_factory=set)
    cooldowns: Dict[str, float] = field(default_factory=dict)

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

    def _cooling(self, model: str, now: Optional[float]) -> bool:
        """True if ``model`` is still on a server-overload cooldown at ``now`` (epoch s).

        When ``now`` is ``None`` cooldowns are ignored (backward-compatible with the
        original daily-only callers that pass no clock)."""
        if now is None:
            return False
        until = self.cooldowns.get(model)
        return until is not None and until > now

    @property
    def all_exhausted(self) -> bool:
        """All models daily-quota walled (ignores transient cooldowns)."""
        return all(m in self.exhausted for m in self.models)

    @property
    def current(self) -> str:
        """First non-exhausted model (daily walls only; cooldowns ignored).

        Backward-compatible no-arg property. Use :meth:`current_or_none(now=...)` to
        also skip models that are temporarily cooling down.
        """
        m = self.current_or_none()
        if m is None:
            raise AllModelsExhausted("every model is exhausted-for-today")
        return m

    def mark_exhausted(self, model: Optional[str] = None) -> None:
        target = (model or self.current_or_none() or "").strip()
        if target:
            self.exhausted.add(target)

    def mark_overloaded(
        self,
        model: str,
        *,
        now: float,
        cooldown_seconds: float = DEFAULT_OVERLOAD_COOLDOWN_SECONDS,
    ) -> None:
        """Put ``model`` on a temporary cooldown until ``now + cooldown_seconds`` (epoch s).

        Distinct from :meth:`mark_exhausted`: this is a transient server-overload step-off,
        not a daily wall. ``now`` is supplied by the caller (pure)."""
        target = (model or "").strip()
        if not target:
            return
        self.cooldowns[target] = now + max(0.0, cooldown_seconds)

    def current_or_none(self, now: Optional[float] = None) -> Optional[str]:
        """First model available at ``now``: neither daily-walled nor cooling down.

        ``now`` is epoch seconds; omit it to consider daily walls only (cooldowns
        ignored) — preserves the original signature for daily-only callers."""
        for m in self.models:
            if m not in self.exhausted and not self._cooling(m, now):
                return m
        return None

    def advance(self, now: Optional[float] = None) -> str:
        """Return the next live model (daily-walled AND cooldown-aware when ``now`` given).

        Raises :class:`AllModelsExhausted` when nothing is available right now."""
        nxt = self.current_or_none(now)
        if nxt is None:
            raise AllModelsExhausted("every model is exhausted-for-today")
        return nxt

    def seconds_until_any_available(self, now: float) -> Optional[float]:
        """Soonest moment a model frees up, as seconds-from-``now`` (>= 0).

        Returns ``None`` when a model is already available at ``now`` (nothing to wait
        for), or when the only blockers are *daily* quota walls (no cooldown to expire —
        the caller should fall back to the Pacific-midnight wait). When every available
        path is gated purely by cooldowns, returns the seconds until the earliest expiry.
        """
        if self.current_or_none(now) is not None:
            return None
        # Earliest future cooldown expiry among models that are NOT daily-walled
        # (a daily-walled model won't come back on its cooldown clock).
        soonest: Optional[float] = None
        for m in self.models:
            if m in self.exhausted:
                continue
            until = self.cooldowns.get(m)
            if until is None or until <= now:
                continue
            if soonest is None or until < soonest:
                soonest = until
        if soonest is None:
            return None
        return max(0.0, soonest - now)

    def clear_expired_cooldowns(self, now: float) -> None:
        """Drop cooldown entries that have expired at ``now`` (epoch s)."""
        for m in [m for m, until in self.cooldowns.items() if until <= now]:
            del self.cooldowns[m]

    def reset(self) -> None:
        """Clear the daily exhausted set (after the Pacific quota reset).

        Cooldowns are intentionally left alone — they expire on their own clock."""
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
    FROM event_youtube_with_jurisdiction v
    JOIN bronze.bronze_event_youtube_transcript t
        ON t.video_id = v.video_id
       AND t.has_transcript IS TRUE
       AND COALESCE(t.transcript_source, '') NOT LIKE 'excluded:%%'
    WHERE v.policy_analysis_at IS NULL
      AND COALESCE(v.jurisdiction_id, '') <> ''
      AND v.video_url IS NOT NULL
      AND BTRIM(v.video_url) <> ''
      AND UPPER(COALESCE(v.meeting_type, '')) NOT IN ('OTHER', 'UNKNOWN', '')
      AND NOT EXISTS (
        SELECT 1 FROM bronze.bronze_youtube_channel_classification c
        WHERE c.channel_id = v.channel_id AND c.is_junk IS TRUE
      )
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


def parse_states(spec: Optional[Sequence[str]]) -> List[str]:
    """Parse repeated/comma-separated ``--state`` values into upper 2-letter codes.

    Accepts a list of raw argparse values (each may itself be comma-separated), e.g.
    ``["GA,AL", "wi"]`` -> ``["GA", "AL", "WI"]``. De-duplicates, preserves order.
    """
    if not spec:
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in spec:
        for piece in str(raw or "").split(","):
            code = piece.strip().upper()
            if code and code not in seen:
                seen.add(code)
                out.append(code)
    return out


def parse_shard(spec: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse a ``--shard i/n`` spec into ``(index, count)`` with ``0 <= index < count``.

    Returns ``None`` when unset. Raises ``ValueError`` on a malformed / out-of-range spec
    so the operator gets a clear failure instead of a silently-wrong partition.
    """
    if not spec or not str(spec).strip():
        return None
    text = str(spec).strip()
    if "/" not in text:
        raise ValueError(f"--shard expects 'i/n' (e.g. 0/3), got {spec!r}")
    i_str, n_str = text.split("/", 1)
    try:
        index, count = int(i_str.strip()), int(n_str.strip())
    except ValueError as exc:
        raise ValueError(f"--shard expects integers 'i/n', got {spec!r}") from exc
    if count <= 0:
        raise ValueError(f"--shard count must be >= 1, got {count}")
    if not (0 <= index < count):
        raise ValueError(f"--shard index must satisfy 0 <= i < n, got {index}/{count}")
    return index, count


def _stable_shard_bucket(jurisdiction_id: str, count: int) -> int:
    """Deterministic, process-independent bucket in ``[0, count)`` for a jurisdiction.

    Uses an MD5 digest (not Python's salted ``hash``) so separate shard processes —
    each its own interpreter — agree on the partition. Mirrors Postgres ``hashtext``'s
    intent (a stable hash of the id) without depending on the DB.
    """
    import hashlib

    digest = hashlib.md5(jurisdiction_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % count


def filter_plans(
    plans: Sequence[JurisdictionPlan],
    *,
    states: Optional[Sequence[str]] = None,
    shard: Optional[Tuple[int, int]] = None,
) -> List[JurisdictionPlan]:
    """Apply the jurisdiction-slice filters in the pure layer (unit-testable).

    * ``states`` — keep only plans whose ``state_code`` is in the (upper-cased) set.
    * ``shard`` — ``(index, count)``; keep only plans whose stable hash bucket matches
      ``index`` so ``count`` disjoint processes partition the backlog without overlap.

    Recency order is preserved.
    """
    state_set = {s.strip().upper() for s in (states or []) if s and s.strip()}
    out: List[JurisdictionPlan] = []
    for p in plans:
        if state_set and p.state_code.upper() not in state_set:
            continue
        if shard is not None:
            index, count = shard
            if _stable_shard_bucket(p.jurisdiction_id, count) != index:
                continue
        out.append(p)
    return out


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


def fetch_pending_plans(
    database_url: str, *, states: Optional[Sequence[str]] = None
) -> List[JurisdictionPlan]:
    """Run the recency work-list query and build the jurisdiction plan.

    ``states`` (2-letter codes) pushes a ``state_code IN (...)`` filter into the SQL so a
    state-sliced run scans only its own jurisdictions instead of the whole backlog.
    """
    import os

    import psycopg2

    # The work-list view (event_youtube_with_jurisdiction) lives in the full-warehouse
    # DATA schema, which is `gold` on the split warehouse and `public` on a non-split
    # one. Mirror api/database.py: reference the view UNqualified and resolve it via
    # search_path (data schema first, public fallback). bronze.* refs stay explicit.
    data_schema = (os.getenv("API_DB_SCHEMA") or "gold").strip() or "gold"
    search_path = data_schema if data_schema == "public" else f"{data_schema},public"

    state_codes = parse_states(list(states) if states else None)
    sql = PENDING_BY_JURISDICTION_SQL
    params: Tuple = ()
    if state_codes:
        # Inject the IN-filter before GROUP BY; parameterised to avoid injection.
        placeholders = ", ".join(["%s"] * len(state_codes))
        sql = sql.replace(
            "    GROUP BY v.jurisdiction_id",
            f"      AND UPPER(COALESCE(v.state_code, '')) IN ({placeholders})\n"
            "    GROUP BY v.jurisdiction_id",
        )
        params = tuple(state_codes)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {search_path}")
            cur.execute(sql, params)
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
    prompt_file: str = "",
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
    if prompt_file:
        ns.prompt_file = prompt_file
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
    cooldown_seconds = float(
        getattr(args, "overload_cooldown_seconds", None) or DEFAULT_OVERLOAD_COOLDOWN_SECONDS
    )

    states = parse_states(getattr(args, "state", None))
    shard = parse_shard(getattr(args, "shard", None))

    plans = fetch_pending_plans(database_url, states=states)
    plans = filter_plans(plans, states=states, shard=shard)
    total_pending = sum(p.pending for p in plans)
    if args.max_jurisdictions is not None:
        plans = plans[: int(args.max_jurisdictions)]

    if states:
        logger.info("State slice: {}", ", ".join(states))
    if shard is not None:
        logger.info("Shard slice: {}/{}", shard[0], shard[1])
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
    quota_giveup = _quota_giveup_type()
    overload_giveup = _overload_giveup_type()
    unavailable_giveup = _model_unavailable_giveup_type()
    for plan in plans:
        # Retry the same jurisdiction across models until it completes or all models wall.
        while True:
            # Pick a model that is neither daily-walled nor cooling down right now.
            live_model = cycler.current_or_none(now=time.time())
            if live_model is None:
                if not _handle_all_unavailable(args, cycler):
                    logger.success("Exiting on quota exhaustion (--on-exhaust exit).")
                    return
                continue
            ns = build_pipeline_namespace(
                plan,
                model=live_model,
                database_url=database_url,
                limit=args.limit_per_jurisdiction,
                prompt_file=getattr(args, "prompt_file", "") or "",
            )
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
            except unavailable_giveup as exc:
                # A retired/unknown model (404 NOT_FOUND). It will never come back, so
                # drop it from the rotation PERMANENTLY for the run (mark_exhausted, like a
                # daily wall but never reset back in by reset() — a re-rotation onto it
                # would just re-detect the 404 and re-drop it via this same path) and retry
                # the same jurisdiction on the next live model.
                logger.warning(
                    "Model {} is unavailable (retired) — dropping from rotation on {}: {}",
                    model,
                    plan.jurisdiction_id,
                    exc,
                )
                cycler.mark_exhausted(model)
                try:
                    cycler.advance(now=time.time())
                except AllModelsExhausted:
                    # Every model is now dead/walled — fall through to the existing
                    # all-unavailable handling at the top of the loop.
                    pass
                # Loop again: next live model is picked at the top (or all-exhausted path).
                continue
            except quota_giveup as exc:
                logger.warning(
                    "Model {} hit the daily quota wall on {}: {}",
                    model,
                    plan.jurisdiction_id,
                    exc,
                )
                cycler.mark_exhausted(model)
                # Loop again: next live model is picked at the top (cooldown-aware).
                continue
            except overload_giveup as exc:
                logger.warning(
                    "Model {} is server-overloaded on {} — cooling down {} and rotating: {}",
                    model,
                    plan.jurisdiction_id,
                    format_eta(cooldown_seconds),
                    exc,
                )
                cycler.mark_overloaded(
                    model, now=time.time(), cooldown_seconds=cooldown_seconds
                )
                # Loop again: pick the next live model (or short-wait if all cooling down).
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


def _overload_giveup_type():
    from llm.gemini.genai_text_client import GenAIServerOverloadGiveUp

    return GenAIServerOverloadGiveUp


def _model_unavailable_giveup_type():
    from llm.gemini.genai_text_client import GenAIModelUnavailableGiveUp

    return GenAIModelUnavailableGiveUp


def _handle_all_unavailable(args: argparse.Namespace, cycler: ModelCycler) -> bool:
    """No model is usable right now. Return True to keep going (after waiting), False to exit.

    Distinguishes two cases the cooldown work introduced:

    * **Some models are merely cooling down** (transient server overload): sleep only
      until the soonest cooldown expiry, clear expired cooldowns, and resume. Do NOT
      wait until Pacific midnight for a transient congestion blip.
    * **Every model is daily-quota walled**: fall back to the original Pacific-midnight
      wait + daily reset.

    ``--on-exhaust exit`` short-circuits both to a clean exit.
    """
    if args.on_exhaust == "exit":
        return False

    cooldown_wait = cycler.seconds_until_any_available(time.time())
    if cooldown_wait is not None:
        # At least one model is only cooling down (not daily-walled): short wait.
        logger.warning(
            "All live models are server-overloaded (cooling down). Sleeping {} "
            "until the soonest model frees up.",
            format_eta(cooldown_wait),
        )
        # +2s slack so the cooldown has definitely elapsed when we re-check.
        time.sleep(cooldown_wait + 2.0)
        cycler.clear_expired_cooldowns(time.time())
        logger.info("Cooldown elapsed — resuming model rotation.")
        return True

    # Nothing cooling down => the blockers are daily quota walls. Wait for the reset.
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
        "--prompt-file",
        default="",
        help="Part-1 prompt passed through to run_pipeline (default: pipeline default). "
        "Use prompts/policy_analysis_lite.md for the cheap decisions+classification pass.",
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
        "(default) or exit cleanly. (Transient server-overload cooldowns always short-wait.)",
    )
    parser.add_argument(
        "--state",
        action="append",
        default=None,
        metavar="CODE",
        help="Restrict the backlog to these 2-letter state codes. Repeatable and/or "
        "comma-separated (e.g. --state GA --state AL  or  --state GA,AL). Pushes a "
        "state_code IN (...) filter into the work-list SQL.",
    )
    parser.add_argument(
        "--shard",
        default=None,
        metavar="i/n",
        help="Partition jurisdictions into n disjoint shards and process only shard i "
        "(0-based), via a stable hash of jurisdiction_id. Run n processes (--shard 0/3, "
        "--shard 1/3, …) for clean multi-process parallelism with no overlap.",
    )
    parser.add_argument(
        "--overload-cooldown-seconds",
        type=float,
        default=DEFAULT_OVERLOAD_COOLDOWN_SECONDS,
        help="Seconds to temporarily step a model off the rotation after a sustained "
        f"server-overload give-up (502/503/504). Default: {int(DEFAULT_OVERLOAD_COOLDOWN_SECONDS)}.",
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
