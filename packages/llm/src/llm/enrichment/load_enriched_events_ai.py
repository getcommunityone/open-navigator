#!/usr/bin/env python3
"""
Master AI Enrichment Runner

Runs the AI enrichment pipeline in sequence: analyze meeting transcripts with
Gemini, then merge bronze AI extractions to production tables.

Steps (run in order):
  1. analyze  — Meeting Transcripts (Gemini AI)  → llm/enrichment/load_meeting_transcripts.py
  2. merge    — Bronze → Production              → llm/enrichment/merge_bronze_to_production.py

MOA synthesis (moa_synthesize.py) is per-event and must be run separately:
  .venv/bin/python -m llm.enrichment.moa_synthesize --event-id <id> --aggregator claude-opus

Usage:
    python -m llm.enrichment.load_enriched_events_ai                          # all steps, priority states
    python -m llm.enrichment.load_enriched_events_ai --states MA,WI,GA        # specific states
    python -m llm.enrichment.load_enriched_events_ai --all-states             # every state with known channels
    python -m llm.enrichment.load_enriched_events_ai --only analyze           # analysis only, skip merge
    python -m llm.enrichment.load_enriched_events_ai --skip merge             # skip merge
    python -m llm.enrichment.load_enriched_events_ai --dry-run                # no API calls or DB writes
    python -m llm.enrichment.load_enriched_events_ai --force                  # re-analyze already-processed meetings
    python -m llm.enrichment.load_enriched_events_ai --model gemini-2.5-flash --meetings-per-channel 10
"""
import sys
import os
import subprocess
import argparse
import time
import threading
from datetime import datetime
from pathlib import Path

import psycopg2
from loguru import logger

sys.path.insert(0, str(Path(__file__).parents[5]))
from scripts.utils.log_sync import sync_logs, MACHINE_ID


PROJECT_ROOT = Path(__file__).parents[5]
LOG_ROOT = PROJECT_ROOT / "logs" / "enrich_ai"

_PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{_PG_PASSWORD}@localhost:5433/open_navigator"

STEPS = [
    {
        "key": "analyze",
        "label": "Meeting Transcripts (Gemini AI)",
        "module": "llm.enrichment.load_meeting_transcripts",
        "supports_dry_run": True,
        "tables": ["bronze.bronze_events_analysis_ai"],
    },
    {
        "key": "merge",
        "label": "Bronze → Production Merge",
        "module": "llm.enrichment.merge_bronze_to_production",
        "supports_dry_run": True,
        # Production tables live in Neon (separate DB); count bronze side as proxy
        "tables": ["bronze.bronze_events_analysis_ai"],
    },
]


def count_rows(tables: list[str]) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                counts[table] = None
        cur.close()
        conn.close()
    except Exception:
        counts = {t: None for t in tables}
    return counts


def total_count(counts: dict[str, int | None]) -> int | None:
    vals = [v for v in counts.values() if v is not None]
    return sum(vals) if vals else None


def stream_to_file(stream, log_file, also_stdout: bool = True) -> None:
    for line in iter(stream.readline, ""):
        if also_stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        log_file.write(line)
    log_file.flush()


def run_subprocess(cmd: list, log_path: Path, cwd: Path = PROJECT_ROOT) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as log_file:
        proc = subprocess.Popen(
            cmd, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        t = threading.Thread(target=stream_to_file, args=(proc.stdout, log_file))
        t.start()
        proc.wait()
        t.join()
    return proc.returncode


def run_step(step: dict, extra_args: list[str], dry_run: bool, log_dir: Path) -> dict:
    tables = step.get("tables", [])
    before = count_rows(tables)

    cmd = [sys.executable, "-m", step["module"]]
    cmd.extend(extra_args)
    if dry_run and step["supports_dry_run"]:
        cmd.append("--dry-run")

    log_path = log_dir / f"{step['key']}.log"
    logger.info(f"$ {' '.join(str(c) for c in cmd)}")
    logger.info(f"  log → {log_path.relative_to(PROJECT_ROOT)}")

    start = time.monotonic()
    exit_code = run_subprocess(cmd, log_path)
    elapsed = time.monotonic() - start

    after = count_rows(tables)

    return {
        "key": step["key"],
        "label": step["label"],
        "exit_code": exit_code,
        "elapsed": elapsed,
        "ok": exit_code == 0,
        "dry_run": dry_run and step["supports_dry_run"],
        "tables": tables,
        "before": before,
        "after": after,
        "log_path": log_path,
    }


def fmt_elapsed(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.1f}s" if m else f"{s:.1f}s"


def fmt_count(n: int | None) -> str:
    return f"{n:>12,}" if n is not None else f"{'—':>12}"


def fmt_delta(before: int | None, after: int | None) -> str:
    if after is None:
        return f"{'—':>12}"
    delta = after - (before or 0)
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:,}".rjust(12)


def print_summary(results: list[dict], started_at: datetime, log_dir: Path) -> None:
    duration = (datetime.now() - started_at).total_seconds()
    n_ok = sum(1 for r in results if r["ok"])
    n_skipped = sum(1 for r in results if r.get("skipped"))
    n_failed = len(results) - n_ok - n_skipped

    sep = "=" * 80
    thin = "-" * 80

    logger.info("")
    logger.info(sep)
    logger.info("  AI ENRICHMENT SUMMARY")
    logger.info(f"  Started : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ({fmt_elapsed(duration)} total)")
    logger.info(f"  Logs    : {log_dir.relative_to(PROJECT_ROOT)}/")
    logger.info(thin)
    logger.info(f"  {'STATUS':<10}  {'TIME':>8}  {'ADDED':>12}  {'TOTAL':>12}  STEP")
    logger.info(thin)

    for r in results:
        if r.get("skipped"):
            tag = "SKIP"
        elif r["ok"]:
            tag = "OK"
        else:
            tag = f"FAIL({r['exit_code']})"

        notes = []
        if r.get("dry_run"):
            notes.append("dry-run")
        label_suffix = f"  [{', '.join(notes)}]" if notes else ""

        before_total = total_count(r.get("before", {}))
        after_total = total_count(r.get("after", {}))

        logger.info(
            f"  {tag:<10}  {fmt_elapsed(r['elapsed']):>8}"
            f"  {fmt_delta(before_total, after_total)}"
            f"  {fmt_count(after_total)}"
            f"  {r['label']}{label_suffix}"
        )

        log_path = r.get("log_path")
        if log_path:
            rel = log_path.relative_to(PROJECT_ROOT)
            if not r["ok"] and not r.get("skipped"):
                logger.error(f"  {'':10}  {'':8}  {'':12}  {'':12}    log → {rel}")
            else:
                logger.info(f"  {'':10}  {'':8}  {'':12}  {'':12}    log → {rel}")

    logger.info(thin)
    parts = [f"{n_ok} succeeded"]
    if n_failed:
        parts.append(f"{n_failed} failed")
    if n_skipped:
        parts.append(f"{n_skipped} skipped")
    summary_line = ",  ".join(parts)

    if n_failed:
        logger.error(f"  {summary_line}")
    else:
        logger.success(f"  {summary_line}")
    logger.info(sep)

    if not any(r.get("skipped") for r in results if r["key"] == "merge"):
        logger.info("")
        logger.info("  Next step for per-event synthesis:")
        logger.info("  .venv/bin/python -m llm.enrichment.moa_synthesize \\")
        logger.info("      --event-id <id> --aggregator claude-opus")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AI enrichment pipeline: analyze meetings → merge to production",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    keys = [s["key"] for s in STEPS]
    parser.add_argument(
        "--skip", nargs="+", choices=keys, metavar="KEY",
        help=f"Steps to skip. Choices: {', '.join(keys)}",
    )
    parser.add_argument(
        "--only", nargs="+", choices=keys, metavar="KEY",
        help="Run only these steps (mutually exclusive with --skip)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No API calls or DB writes (passed to steps that support it)",
    )

    # Passthrough args for the analyze step
    analyze_group = parser.add_argument_group("analyze step options")
    state_group = analyze_group.add_mutually_exclusive_group()
    state_group.add_argument(
        "--states", type=str, metavar="MA,WI,GA",
        help="Comma-separated state codes to analyze",
    )
    state_group.add_argument(
        "--all-states", action="store_true",
        help="Analyze all states with known channels (slow — omit for priority states only)",
    )
    analyze_group.add_argument(
        "--meetings-per-channel", type=int, default=5, metavar="N",
        help="Meetings to analyze per channel (default: 5)",
    )
    analyze_group.add_argument(
        "--model", type=str, default="gemini-3.1-flash-lite-preview",
        choices=[
            "gemini-3.1-flash-lite-preview",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        help="Gemini model (default: gemini-3.1-flash-lite-preview — 1,500 req/day free)",
    )
    analyze_group.add_argument(
        "--force", action="store_true",
        help="Re-analyze meetings that were already processed",
    )
    analyze_group.add_argument(
        "--delay", type=float, default=5.0, metavar="SECS",
        help="Seconds between API requests (default: 5.0 for free-tier rate limit)",
    )

    # Passthrough args for the merge step
    merge_group = parser.add_argument_group("merge step options")
    merge_group.add_argument(
        "--entity",
        choices=["contacts", "organizations", "bills", "all"],
        default="all",
        help="Entity type to merge (default: all)",
    )

    args = parser.parse_args()

    if args.skip and args.only:
        parser.error("--skip and --only are mutually exclusive")

    started_at = datetime.now()
    run_id = started_at.strftime("%Y%m%d_%H%M%S")
    log_dir = LOG_ROOT / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    orchestrator_log = log_dir / "orchestrator.log"
    logger.add(orchestrator_log, level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    logger.info("=" * 80)
    logger.info("  OPEN NAVIGATOR — AI ENRICHMENT")
    logger.info(f"  {started_at.strftime('%Y-%m-%d %H:%M:%S')}  (run: {run_id})  machine: {MACHINE_ID}")
    logger.info("=" * 80)

    steps = list(STEPS)
    if args.only:
        steps = [s for s in steps if s["key"] in args.only]
    elif args.skip:
        steps = [s for s in steps if s["key"] not in args.skip]

    if args.dry_run:
        logger.warning("--dry-run active: no API calls or DB writes")

    # Build per-step extra args
    analyze_args = [
        "--meetings-per-channel", str(args.meetings_per_channel),
        "--model", args.model,
        "--delay", str(args.delay),
    ]
    if args.states:
        analyze_args += ["--states", args.states]
    elif not args.all_states:
        analyze_args.append("--priority-states")
    if args.force:
        analyze_args.append("--force")

    merge_args = ["--entity", args.entity]

    step_args = {
        "analyze": analyze_args,
        "merge": merge_args,
    }

    results: list[dict] = []

    for step in steps:
        logger.info("")
        logger.info(f"  {'─' * 76}")
        logger.info(f"  ▶  {step['label']}")
        logger.info(f"  {'─' * 76}")
        result = run_step(step, extra_args=step_args.get(step["key"], []), dry_run=args.dry_run, log_dir=log_dir)
        results.append(result)
        if not result["ok"]:
            logger.error(f"  Step exited with code {result['exit_code']} — continuing to next step")

    print_summary(results, started_at, log_dir)
    sync_logs(log_dir, run_type="enrich_ai", project_root=PROJECT_ROOT)

    failed = [r for r in results if not r["ok"] and not r.get("skipped")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
