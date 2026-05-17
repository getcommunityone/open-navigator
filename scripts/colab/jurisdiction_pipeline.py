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

import gatekeeper_triage
from colab_demos import DemoContext, JurisdictionDemoReports, run_demos_for_jurisdiction
from governance_meeting_llm import MeetingInventory, inventory_for_jurisdiction

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
    demo_date_cap: Optional[int] = None
    gatekeeper_max_files: Optional[int] = None
    organize_meetings: bool = True


def scope_inventory(
    inv: MeetingInventory,
    raw_root: Path,
    *,
    max_dates: Optional[int],
) -> MeetingInventory:
    """Apply DEMO date scope to one inventory."""
    if max_dates is None:
        return inv
    try:
        from meeting_date_scope import filter_inventory_media
    except ImportError:
        return inv
    inv.pdfs, inv.audio = filter_inventory_media(
        inv.pdfs, inv.audio, raw_root, inv.jurisdiction.root, max_dates=max_dates
    )
    return inv


def organize_inventory(raw_root: Path, inv: MeetingInventory) -> int:
    try:
        from meeting_grouping import organize_inventory_into_meeting_folders
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

    total = gatekeeper_triage.count_triageable_files(
        ctx.raw_root, kinds=kinds, jurisdiction_root=jur_root
    )
    triage_paths, _n, allowed_dates, _years = gatekeeper_triage.select_triageable_files(
        ctx.raw_root,
        kinds=kinds,
        max_files=ctx.gatekeeper_max_files,
        jurisdiction_root=jur_root,
    )
    print(
        f"  Gatekeeper | {label} | candidates={total} | will_triage={len(triage_paths)}",
        flush=True,
    )
    if allowed_dates and label in allowed_dates:
        print(f"    dates: {', '.join(sorted(allowed_dates[label]))}", flush=True)

    slug = _log_slug(label)
    log_path = logs_dir / f"gatekeeper_{slug}_{stamp}.log"

    with _gatekeeper_log_lock:
        gatekeeper_triage.configure_logging(
            verbose=True,
            log_path=log_path,
            console=True,
        )
        try:
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

    run_gatekeeper_for_jurisdiction(inv, ctx, stamp=stamp, logs_dir=logs_dir)
    inv = reload_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)
    if not inv.has_media:
        print(f"  No media left after Gatekeeper for {label}.", flush=True)
        return JurisdictionDemoReports()

    if ctx.organize_meetings and os.environ.get("GOVERNANCE_ORGANIZE_MEETINGS", "1") == "1":
        n_moves = organize_inventory(ctx.raw_root, inv)
        if n_moves:
            print(f"  Organized {n_moves} file(s) into meetings/…", flush=True)
            inv = reload_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)

    print(
        f"  Demos | pdfs={len(inv.pdfs)} audio={len(inv.audio)} images={len(inv.images)}",
        flush=True,
    )
    reports = run_demos_for_jurisdiction(inv, ctx.demo_ctx, brief_cache=brief_cache)
    print(
        f"\n  ✓ Finished {label} — outputs under {ctx.demo_ctx.processed_root.name}/",
        flush=True,
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
    return all_reports


# Notebook import alias
run_per_jurisdiction_e2e = run_governance_pipeline
