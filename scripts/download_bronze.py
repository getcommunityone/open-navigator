#!/usr/bin/env python3
"""
Master Bronze Download Runner

Downloads all source data files to the local cache before bronze ingestion.
Each step's stdout/stderr is streamed to the terminal AND saved to a timestamped
log file under logs/download_bronze/<run_id>/.

Downloaders (run in order):
  1. gazetteer        — Jurisdictions (Gazetteer → gold parquet)   → census/download_census_gazetteer.py
  2. shapefiles       — Boundary shapefiles (states/counties/zcta/places) → census/download_census_shapefiles.py
  3. school_districts — School district shapefiles (TIGER/Line)    → census/download_census_school_districts.py
  4. relationships    — ZCTA-County / ZCTA-Place crosswalks        → census/download_census_relationships.py
  5. municipalities   — Municipalities Gazetteer CSV               → census/download_census_municipalities.py

Usage:
    python scripts/download_bronze.py                          # download everything
    python scripts/download_bronze.py --only shapefiles        # one step only
    python scripts/download_bronze.py --skip gazetteer         # skip one step
    python scripts/download_bronze.py --force                  # re-download even if cached
    python scripts/download_bronze.py --extract                # extract shapefile ZIPs after download
    python scripts/download_bronze.py --year 2024              # use a different Census vintage year
    python scripts/download_bronze.py --dry-run                # print commands without running
    python scripts/download_bronze.py --retry-failed           # re-run only steps that failed last time
    python scripts/download_bronze.py --retry-run 20260507_120000
"""
import sys
import json
import subprocess
import argparse
import time
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils.log_sync import sync_logs, MACHINE_ID


PROJECT_ROOT = Path(__file__).parent.parent
LOG_ROOT = PROJECT_ROOT / "logs" / "download_bronze"

DOWNLOADERS = [
    {
        "key": "gazetteer",
        "label": "Jurisdictions Gazetteer (Census → gold parquet)",
        "script": "scripts/datasources/census/download_census_gazetteer.py",
        "cache_dirs": ["data/cache/census/gazetteer", "data/gold"],
        "supports_force": False,
        "supports_year": False,
        "supports_extract": False,
    },
    {
        "key": "shapefiles",
        "label": "Boundary Shapefiles (states / counties / zcta / places)",
        "script": "scripts/datasources/census/download_census_shapefiles.py",
        "cache_dirs": ["data/cache/census/shapefiles"],
        "supports_force": False,
        "supports_year": True,
        "supports_extract": True,
    },
    {
        "key": "school_districts",
        "label": "School District Shapefiles (unified / elementary / secondary)",
        "script": "scripts/datasources/census/download_census_school_districts.py",
        "cache_dirs": ["data/cache/census/school_districts"],
        "supports_force": False,
        "supports_year": True,
        "supports_extract": True,
    },
    {
        "key": "relationships",
        "label": "Geographic Relationships (ZCTA-County, ZCTA-Place)",
        "script": "scripts/datasources/census/download_census_relationships.py",
        "cache_dirs": ["data/cache/census_relationships"],
        "supports_force": True,
        "supports_year": False,
        "supports_extract": False,
    },
    {
        "key": "municipalities",
        "label": "Municipalities Gazetteer CSV (Census Places)",
        "script": "scripts/datasources/census/download_census_municipalities.py",
        "cache_dirs": ["data/cache/census"],
        "supports_force": True,
        "supports_year": False,
        "supports_extract": False,
    },
]


# ---------------------------------------------------------------------------
# Results persistence
# ---------------------------------------------------------------------------

def save_results(results: list[dict], log_dir: Path, started_at: datetime) -> None:
    payload = {
        "run_id": log_dir.name,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now().isoformat(),
        "steps": [
            {
                "key": r["key"],
                "label": r["label"],
                "ok": r["ok"],
                "exit_code": r["exit_code"],
                "elapsed": round(r["elapsed"], 2),
            }
            for r in results
        ],
    }
    (log_dir / "results.json").write_text(json.dumps(payload, indent=2))


def load_failed_keys(run_id: str | None) -> tuple[list[str], str]:
    if run_id:
        run_dir = LOG_ROOT / run_id
    else:
        runs = sorted(LOG_ROOT.iterdir()) if LOG_ROOT.exists() else []
        runs = [r for r in runs if r.is_dir() and (r / "results.json").exists()]
        if not runs:
            raise FileNotFoundError(f"No completed runs found in {LOG_ROOT}")
        run_dir = runs[-1]

    results_file = run_dir / "results.json"
    if not results_file.exists():
        raise FileNotFoundError(f"No results.json in {run_dir}. Was this run completed?")

    data = json.loads(results_file.read_text())
    failed = [s["key"] for s in data["steps"] if not s["ok"]]
    return failed, data["run_id"]


# ---------------------------------------------------------------------------
# Cache size helpers
# ---------------------------------------------------------------------------

def dir_size_bytes(dirs: list[str]) -> int:
    total = 0
    for d in dirs:
        p = PROJECT_ROOT / d
        if p.exists():
            total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return total


def fmt_bytes(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Downloader runner
# ---------------------------------------------------------------------------

def run_downloader(
    downloader: dict,
    force: bool,
    extract: bool,
    year: int,
    dry_run: bool,
    log_dir: Path,
) -> dict:
    cache_dirs = downloader.get("cache_dirs", [])
    size_before = dir_size_bytes(cache_dirs)

    cmd = [sys.executable, downloader["script"]]

    if year and downloader["supports_year"]:
        cmd += ["--year", str(year)]
    if force and downloader["supports_force"]:
        cmd.append("--force")
    if extract and downloader["supports_extract"]:
        cmd.append("--extract")

    log_path = log_dir / f"{downloader['key']}.log"
    logger.info(f"$ {' '.join(str(c) for c in cmd)}")
    logger.info(f"  log → {log_path.relative_to(PROJECT_ROOT)}")

    if dry_run:
        logger.info("  [dry-run] skipping execution")
        return {
            "key": downloader["key"],
            "label": downloader["label"],
            "exit_code": 0,
            "elapsed": 0.0,
            "ok": True,
            "dry_run": True,
            "size_before": size_before,
            "size_after": size_before,
            "log_path": None,
        }

    start = time.monotonic()
    exit_code = run_subprocess(cmd, log_path)
    elapsed = time.monotonic() - start

    size_after = dir_size_bytes(cache_dirs)

    return {
        "key": downloader["key"],
        "label": downloader["label"],
        "exit_code": exit_code,
        "elapsed": elapsed,
        "ok": exit_code == 0,
        "dry_run": False,
        "size_before": size_before,
        "size_after": size_after,
        "log_path": log_path,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def fmt_elapsed(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.1f}s" if m else f"{s:.1f}s"


def print_summary(results: list[dict], started_at: datetime, log_dir: Path) -> None:
    duration = (datetime.now() - started_at).total_seconds()
    n_ok = sum(1 for r in results if r["ok"])
    n_failed = len(results) - n_ok

    sep = "=" * 80
    thin = "-" * 80

    logger.info("")
    logger.info(sep)
    logger.info("  BRONZE DOWNLOAD SUMMARY")
    logger.info(f"  Started : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ({fmt_elapsed(duration)} total)")
    logger.info(f"  Logs    : {log_dir.relative_to(PROJECT_ROOT)}/")
    logger.info(thin)
    logger.info(f"  {'STATUS':<12}  {'TIME':>8}  {'DOWNLOADED':>12}  {'CACHE':>10}  STEP")
    logger.info(thin)

    for r in results:
        tag = "dry-run" if r.get("dry_run") else ("OK" if r["ok"] else f"FAIL({r['exit_code']})")
        added = r["size_after"] - r["size_before"]
        added_str = (f"+{fmt_bytes(added)}" if added > 0 else "cached").rjust(12)
        cache_str = fmt_bytes(r["size_after"]).rjust(10)

        logger.info(
            f"  {tag:<12}  {fmt_elapsed(r['elapsed']):>8}"
            f"  {added_str}"
            f"  {cache_str}"
            f"  {r['label']}"
        )

        log_path = r.get("log_path")
        if log_path and not r["ok"]:
            rel = log_path.relative_to(PROJECT_ROOT)
            logger.error(f"  {'':12}  {'':8}  {'':12}  {'':10}    log → {rel}")

    logger.info(thin)
    if n_failed:
        logger.error(f"  {n_ok} succeeded,  {n_failed} failed")
        logger.info(f"  To retry: python scripts/download_bronze.py --retry-failed")
    else:
        logger.success(f"  {n_ok} succeeded")
    logger.info(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download all bronze source data files to local cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Download everything:
    python scripts/download_bronze.py

  Re-download everything even if cached:
    python scripts/download_bronze.py --force

  Download shapefiles and extract them:
    python scripts/download_bronze.py --only shapefiles school_districts --extract

  Use a different Census vintage year:
    python scripts/download_bronze.py --year 2022

  Preview what would run without downloading:
    python scripts/download_bronze.py --dry-run

  Retry only failed steps from the last run:
    python scripts/download_bronze.py --retry-failed

Available downloaders:
  gazetteer        Jurisdictions Gazetteer (→ gold parquet)
  shapefiles       Boundary shapefiles: states, counties, zcta, places
  school_districts School district shapefiles: unified, elementary, secondary
  relationships    ZCTA-to-County and ZCTA-to-Place crosswalks
  municipalities   Municipalities Gazetteer CSV
        """,
    )

    keys = [d["key"] for d in DOWNLOADERS]

    retry_group = parser.add_mutually_exclusive_group()
    retry_group.add_argument(
        "--retry-failed", action="store_true",
        help="Re-run only the steps that failed in the most recent run",
    )
    retry_group.add_argument(
        "--retry-run", metavar="RUN_ID",
        help="Re-run only the steps that failed in a specific run (e.g. 20260507_120000)",
    )

    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument(
        "--skip", nargs="+", choices=keys, metavar="KEY",
        help=f"Downloaders to skip. Choices: {', '.join(keys)}",
    )
    filter_group.add_argument(
        "--only", nargs="+", choices=keys, metavar="KEY",
        help="Run only these downloaders",
    )

    parser.add_argument(
        "--force", action="store_true",
        help="Re-download files even if they already exist in cache",
    )
    parser.add_argument(
        "--extract", action="store_true",
        help="Extract shapefile ZIP archives after downloading",
    )
    parser.add_argument(
        "--year", type=int, default=2025, metavar="YEAR",
        help="Census vintage year for shapefiles (default: 2025)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print commands that would run without executing them",
    )

    args = parser.parse_args()

    # Resolve --retry-failed / --retry-run into an --only list
    retry_only: list[str] | None = None
    if args.retry_failed or args.retry_run:
        try:
            run_id = args.retry_run if args.retry_run else None
            failed_keys, source_run = load_failed_keys(run_id)
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return 1

        if not failed_keys:
            logger.success(f"Run {source_run} had no failures — nothing to retry.")
            return 0

        retry_only = failed_keys
        logger.info(
            f"Retrying {len(failed_keys)} failed step(s) from run {source_run}: {', '.join(failed_keys)}"
        )

    started_at = datetime.now()
    run_id = started_at.strftime("%Y%m%d_%H%M%S")
    log_dir = LOG_ROOT / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    orchestrator_log = log_dir / "orchestrator.log"
    logger.add(
        orchestrator_log, level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )

    logger.info("=" * 80)
    logger.info("  OPEN NAVIGATOR — BRONZE DOWNLOAD")
    logger.info(f"  {started_at.strftime('%Y-%m-%d %H:%M:%S')}  (run: {run_id})  machine: {MACHINE_ID}")
    logger.info("=" * 80)

    active_keys = retry_only
    downloaders = list(DOWNLOADERS)
    if active_keys is not None:
        downloaders = [d for d in downloaders if d["key"] in active_keys]
    elif args.only:
        downloaders = [d for d in downloaders if d["key"] in args.only]
    elif args.skip:
        downloaders = [d for d in downloaders if d["key"] not in args.skip]

    if args.dry_run:
        logger.warning("--dry-run active: commands will be printed but not executed")
    if args.force:
        logger.info("--force active: cached files will be re-downloaded where supported")
    if args.extract:
        logger.info("--extract active: shapefile ZIPs will be extracted after download")
    logger.info(f"Census year: {args.year}")
    logger.info("")

    results: list[dict] = []

    def checkpoint() -> None:
        save_results(results, log_dir, started_at)
        sync_logs(log_dir, run_type="download_bronze", project_root=PROJECT_ROOT)

    for downloader in downloaders:
        logger.info(f"  {'─' * 76}")
        logger.info(f"  ▶  {downloader['label']}")
        logger.info(f"  {'─' * 76}")
        result = run_downloader(
            downloader,
            force=args.force,
            extract=args.extract,
            year=args.year,
            dry_run=args.dry_run,
            log_dir=log_dir,
        )
        results.append(result)
        if not result["ok"]:
            logger.error(f"  Downloader exited with code {result['exit_code']} — continuing to next step")
        checkpoint()
        logger.info("")

    print_summary(results, started_at, log_dir)

    failed = [r for r in results if not r["ok"]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
