"""
Per-jurisdiction pipeline: Gatekeeper → organize → demos 1–4.

Jurisdictions run sequentially within a state. Multiple states can run in
parallel when ``GOVERNANCE_PARALLEL_STATES`` > 1.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import gatekeeper_triage
from .colab_demos import DemoContext, JurisdictionDemoReports, run_demos_for_jurisdiction
from .colab_timed_steps import log_line, timed_step
from .pipeline_logging import (
    print_demo_run_plan,
    print_gatekeeper_mode_hint,
    print_runtime_estimate,
)
from .governance_meeting_llm import (
    MeetingInventory,
    format_inventory_media_line,
    inventory_for_jurisdiction,
)

_gatekeeper_log_lock = threading.Lock()


def gatekeeper_enabled() -> bool:
    return os.environ.get("GOVERNANCE_GATEKEEPER_ENABLED", "1") != "0"


def gatekeeper_logs_dir(pipe_root: Path) -> Path:
    """All Gatekeeper console logs and triage JSON reports live under ``00_logs/``."""
    logs_dir = pipe_root / "00_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _log_slug(label: str) -> str:
    return label.replace("/", "_").replace("\\", "_")


def _gatekeeper_mirror_log_path(log_path: Path) -> Optional[Path]:
    """
    Duplicate Gatekeeper logs to Colab local disk when the primary path is on Drive.

    Desktop Google Drive sync often lags minutes behind Colab; ``/content/…`` is instant.
    Disable with ``GOVERNANCE_GATEKEEPER_LOG_MIRROR=0``.
    """
    if os.environ.get("GOVERNANCE_GATEKEEPER_LOG_MIRROR", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        return None
    if "/content/drive" not in log_path.as_posix():
        return None
    mirror_root = Path(
        os.environ.get(
            "GOVERNANCE_GATEKEEPER_LOG_MIRROR_DIR",
            "/content/governance_pipeline_local/00_logs",
        )
    ).expanduser()
    return mirror_root / log_path.name


def resolve_parallel_state_workers(num_states: int) -> int:
    """
    Max concurrent state workers. ``1`` = fully sequential.
    Default ``2`` when multiple states are present.
    """
    if num_states <= 1:
        return 1
    raw = os.environ.get("GOVERNANCE_PARALLEL_STATES", "2").strip().lower()
    if raw in ("", "0", "1", "false", "no", "off"):
        return 1
    if raw == "auto":
        return min(num_states, max(2, (os.cpu_count() or 4) // 2))
    try:
        n = int(raw)
    except ValueError:
        n = 2
    return min(max(n, 1), num_states)


def group_inventories_by_state(
    inventories: List[MeetingInventory],
) -> Dict[str, List[MeetingInventory]]:
    by_state: Dict[str, List[MeetingInventory]] = defaultdict(list)
    for inv in inventories:
        by_state[inv.jurisdiction.state_code].append(inv)
    return dict(sorted(by_state.items()))


@dataclass
class JurisdictionRunContext:
    raw_root: Path
    pipe_root: Path
    api_key: str
    gatekeeper_model: str
    demo_ctx: DemoContext
    shield_model: str = ""
    demo_date_cap: Optional[int] = None
    gatekeeper_max_files: Optional[int] = None
    organize_meetings: bool = True
    run_safety_review: bool = True


def scope_inventory(
    inv: MeetingInventory,
    raw_root: Path,
    *,
    max_dates: Optional[int],
) -> MeetingInventory:
    """Apply DEMO date scope, then pipeline media scope (pdf / audio / video)."""
    if max_dates is not None:
        try:
            from .meeting_date_scope import filter_inventory_media
        except ImportError:
            pass
        else:
            inv.pdfs, inv.audio = filter_inventory_media(
                inv.pdfs, inv.audio, raw_root, inv.jurisdiction.root, max_dates=max_dates
            )
    try:
        from .pipeline_media_scope import apply_media_scope_to_inventory

        apply_media_scope_to_inventory(inv)
    except ImportError:
        pass
    return inv


def organize_inventory(raw_root: Path, inv: MeetingInventory) -> int:
    try:
        from .meeting_grouping import organize_inventory_into_meeting_folders
    except ImportError:
        return 0
    moves = organize_inventory_into_meeting_folders(raw_root, [inv])
    return len(moves)


def reload_inventory(
    inv: MeetingInventory,
    raw_root: Path,
    *,
    max_dates: Optional[int],
) -> MeetingInventory:
    """Re-walk disk after Gatekeeper / organize moves."""
    fresh = inventory_for_jurisdiction(raw_root, inv.jurisdiction.root)
    if fresh is None:
        return inv
    return scope_inventory(fresh, raw_root, max_dates=max_dates)


def run_gatekeeper_for_jurisdiction(
    inv: MeetingInventory,
    ctx: JurisdictionRunContext,
    *,
    stamp: str,
    logs_dir: Path,
) -> Optional[gatekeeper_triage.TriageReport]:
    if not gatekeeper_enabled():
        print("  Gatekeeper skipped (GOVERNANCE_GATEKEEPER_ENABLED=0).")
        return None

    kinds = tuple(
        k.strip().lower()
        for k in os.environ.get("GOVERNANCE_GATEKEEPER_KINDS", "pdf,audio").split(",")
        if k.strip()
    )
    dry_run = os.environ.get("GOVERNANCE_GATEKEEPER_DRY_RUN", "0") == "1"
    jur_root = inv.jurisdiction.root
    label = inv.jurisdiction.relative_label
    slug = _log_slug(label)
    log_path = logs_dir / f"gatekeeper_{slug}_{stamp}.log"
    mirror_log = _gatekeeper_mirror_log_path(log_path)
    print(f"  Gatekeeper log (Drive): {log_path}", flush=True)
    if mirror_log is not None:
        print(f"  Gatekeeper log (local, instant): {mirror_log}", flush=True)

    gk_logger = gatekeeper_triage.logger
    with _gatekeeper_log_lock:
        gatekeeper_triage.configure_logging(
            verbose=True,
            log_path=log_path,
            mirror_log_path=mirror_log,
            console=True,
        )
        with timed_step(
            f"Gatekeeper | list & classify files | {label}",
            logger=gk_logger,
        ):
            triage_paths, total, allowed_dates, _years = gatekeeper_triage.select_triageable_files(
                ctx.raw_root,
                kinds=kinds,
                max_files=ctx.gatekeeper_max_files,
                jurisdiction_root=jur_root,
                progress_stdout=True,
            )
            try:
                from .pipeline_media_scope import (
                    filter_paths_for_media_scope,
                    get_active_media_scope,
                )

                scope = get_active_media_scope()
                if scope.key != "all":
                    before = len(triage_paths)
                    triage_paths = filter_paths_for_media_scope(triage_paths, scope)
                    print(
                        f"  Gatekeeper | media scope {scope.key!r}: "
                        f"{before} → {len(triage_paths)} file(s) after filter",
                        flush=True,
                    )
            except ImportError:
                pass
        print(
            f"  Gatekeeper | {label} | candidates={total} | will_triage={len(triage_paths)}",
            flush=True,
        )
        if allowed_dates and label in allowed_dates:
            print(f"    dates: {', '.join(sorted(allowed_dates[label]))}", flush=True)
        try:
            with timed_step(
                f"Gatekeeper | API triage ({len(triage_paths)} file(s)) | {label}",
                logger=gk_logger,
            ):
                report = gatekeeper_triage.run_triage(
                    raw_root=ctx.raw_root,
                    api_key=ctx.api_key,
                    model=ctx.gatekeeper_model,
                    kinds=kinds,
                    pdf_pages=int(os.environ.get("GOVERNANCE_GATEKEEPER_PDF_PAGES", "2")),
                    pdf_dpi=int(os.environ.get("GOVERNANCE_GATEKEEPER_PDF_DPI", "120")),
                    audio_window_seconds=int(
                        os.environ.get("GOVERNANCE_GATEKEEPER_AUDIO_WINDOW", "120")
                    ),
                    confidence_threshold=float(
                        os.environ.get("GOVERNANCE_GATEKEEPER_CONFIDENCE", "0.6")
                    ),
                    dry_run=dry_run,
                    max_files=ctx.gatekeeper_max_files,
                    preload_models=False,
                    progress_stdout=True,
                    log_path=log_path,
                    flush_log_each_file=True,
                    organize_meetings=ctx.organize_meetings
                    and os.environ.get("GOVERNANCE_ORGANIZE_MEETINGS", "1") == "1",
                    jurisdiction_root=jur_root,
                    preselected_paths=triage_paths,
                )
        finally:
            gatekeeper_triage.close_gatekeeper_logging()

    report_path = logs_dir / f"triage_report_{slug}_{stamp}.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  Gatekeeper done | keep={len(report.proceed)} exclude={len(report.excluded)} "
        f"errors={len(report.errors)} → 00_logs/{report_path.name}",
        flush=True,
    )
    return report


def run_one_jurisdiction(
    inv: MeetingInventory,
    ctx: JurisdictionRunContext,
    *,
    idx: int,
    total: int,
    stamp: str,
    logs_dir: Path,
    brief_cache: dict[str, str],
    state_label: str = "",
) -> JurisdictionDemoReports:
    label = inv.jurisdiction.relative_label
    prefix = f"[{state_label}] " if state_label else ""
    banner = f"{'=' * 72}\n  {prefix}[{idx}/{total}] {label}\n{'=' * 72}"
    print(banner, flush=True)
    try:
        from .pipeline_media_scope import print_media_scope_banner

        print_media_scope_banner()
    except ImportError:
        pass

    inv = scope_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)

    with timed_step(f"Gatekeeper | {label}"):
        run_gatekeeper_for_jurisdiction(inv, ctx, stamp=stamp, logs_dir=logs_dir)
    print_gatekeeper_mode_hint()
    with timed_step(f"Reload inventory | {label}"):
        inv = reload_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)
    if not inv.has_media:
        print(f"  No media left after Gatekeeper for {label}.", flush=True)
        return JurisdictionDemoReports()

    if ctx.organize_meetings and os.environ.get("GOVERNANCE_ORGANIZE_MEETINGS", "1") == "1":
        with timed_step(f"Organize meetings/ | {label}"):
            n_moves = organize_inventory(ctx.raw_root, inv)
        if n_moves:
            print(f"  Organized {n_moves} file(s) into meetings/…", flush=True)

    try:
        from .meeting_grouping import (
            reconcile_inventory_media_paths,
            repair_duplicate_date_session_folders,
        )

        repaired = repair_duplicate_date_session_folders(
            ctx.raw_root, label
        )
        with timed_step(f"Reload inventory (pre-demos) | {label}"):
            inv = reload_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)
        n_remapped = reconcile_inventory_media_paths(inv, ctx.raw_root)
        if repaired or n_remapped:
            print(
                f"  Meeting layout: {repaired} duplicate date folder(s) hoisted to "
                f"session/; {n_remapped} inventory path(s) remapped.",
                flush=True,
            )
    except ImportError:
        pass

    try:
        from .pipeline_media_scope import print_scoped_inventory_line

        print_scoped_inventory_line(inv)
    except ImportError:
        log_line(f"Demos | {format_inventory_media_line(inv)}")
    print_demo_run_plan(inv, ctx.raw_root)
    print_runtime_estimate(inv, ctx.demo_ctx)
    reports = run_demos_for_jurisdiction(inv, ctx.demo_ctx, brief_cache=brief_cache)
    log_line(
        f"✓ Finished {label} — outputs under {ctx.demo_ctx.processed_root.name}/",
        prefix="",
    )
    return reports


def _run_state_block(
    state_code: str,
    state_inventories: List[MeetingInventory],
    ctx: JurisdictionRunContext,
    *,
    stamp: str,
    logs_dir: Path,
    global_idx_start: int,
    global_total: int,
) -> List[JurisdictionDemoReports]:
    brief_cache: dict[str, str] = {}
    reports: List[JurisdictionDemoReports] = []
    local_total = len(state_inventories)
    for local_idx, inv in enumerate(state_inventories, 1):
        global_idx = global_idx_start + local_idx - 1
        reports.append(
            run_one_jurisdiction(
                inv,
                ctx,
                idx=global_idx,
                total=global_total,
                stamp=stamp,
                logs_dir=logs_dir,
                brief_cache=brief_cache,
                state_label=state_code,
            )
        )
    return reports


def run_governance_pipeline(
    inventories: List[MeetingInventory],
    ctx: JurisdictionRunContext,
) -> List[JurisdictionDemoReports]:
    """Gatekeeper + organize + demos 1–4 for every jurisdiction."""
    if not inventories:
        print("No jurisdictions with media.")
        return []

    logs_dir = gatekeeper_logs_dir(ctx.pipe_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"Gatekeeper logs & triage reports → {logs_dir}", flush=True)

    by_state = group_inventories_by_state(inventories)
    num_states = len(by_state)
    workers = resolve_parallel_state_workers(num_states)
    global_total = len(inventories)
    try:
        from .demo_scope import get_active_preset

        preset = get_active_preset()
        print(
            f"Scope «{preset.key}» preset guide: {preset.eta} for configured caps "
            f"({global_total} jurisdiction(s) this run).",
            flush=True,
        )
    except ImportError:
        pass

    if workers > 1:
        print(
            f"Pipeline | {global_total} jurisdiction(s) across {num_states} state(s) | "
            f"{workers} state(s) in parallel",
            flush=True,
        )
    else:
        print(
            f"Pipeline | {global_total} jurisdiction(s) | "
            f"Gatekeeper → organize → demos 1–4",
            flush=True,
        )

    all_reports: List[JurisdictionDemoReports] = []
    idx_start = 1

    if workers <= 1:
        for state_code, state_invs in by_state.items():
            all_reports.extend(
                _run_state_block(
                    state_code,
                    state_invs,
                    ctx,
                    stamp=stamp,
                    logs_dir=logs_dir,
                    global_idx_start=idx_start,
                    global_total=global_total,
                )
            )
            idx_start += len(state_invs)
    else:
        futures = {}
        offset = 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for state_code, state_invs in by_state.items():
                fut = pool.submit(
                    _run_state_block,
                    state_code,
                    state_invs,
                    ctx,
                    stamp=stamp,
                    logs_dir=logs_dir,
                    global_idx_start=offset,
                    global_total=global_total,
                )
                futures[fut] = state_code
                offset += len(state_invs)
            for fut in as_completed(futures):
                state_code = futures[fut]
                try:
                    all_reports.extend(fut.result())
                except Exception as exc:
                    print(f"ERROR | state {state_code} | {exc}", flush=True)
                    raise

    print(
        f"\n{'=' * 72}\nAll jurisdictions complete ({global_total}).\n{'=' * 72}",
        flush=True,
    )

    try:
        from .pipeline_output_links import print_pipeline_output_index

        prefixes = [
            inv.jurisdiction.relative_label.replace("\\", "/")
            for inv in inventories
        ]
        print_pipeline_output_index(
            pipe_root=ctx.pipe_root,
            gemma_json_root=ctx.demo_ctx.gemma_json_root,
            summaries_root=ctx.demo_ctx.summaries_root,
            jurisdiction_prefixes=prefixes or None,
        )
    except ImportError:
        pass

    if ctx.run_safety_review:
        try:
            from .colab_safety_review import run_safety_review, safety_review_enabled
        except ImportError:
            safety_review_enabled = lambda: False  # type: ignore[assignment,misc]
            run_safety_review = None  # type: ignore[assignment,misc]
        if safety_review_enabled() and run_safety_review and ctx.shield_model:
            safety_root = ctx.pipe_root / "03_processed_outputs" / "05_safety_review"
            try:
                with timed_step("ShieldGemma safety review (Google API)"):
                    run_safety_review(
                        api_key=ctx.api_key,
                        shield_model=ctx.shield_model,
                        gemma_json_root=ctx.demo_ctx.gemma_json_root,
                        safety_root=safety_root,
                        summaries_root=ctx.demo_ctx.summaries_root,
                    )
            except Exception as exc:
                print(
                    f"⚠️  Safety review skipped ({type(exc).__name__}: {exc}). "
                    "Demo 4 outputs are still on Drive. "
                    "Set GOVERNANCE_SAFETY_REVIEW=0 to silence, or fix Shield model / quota.",
                    flush=True,
                )

    return all_reports


# Notebook import alias
run_per_jurisdiction_e2e = run_governance_pipeline
