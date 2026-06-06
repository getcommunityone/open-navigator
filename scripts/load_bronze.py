#!/usr/bin/env python3
"""
Master Bronze Ingestion Runner

Runs all bronze-layer data loaders in sequence, then triggers dbt bronze models.
Each step's stdout/stderr is streamed to the terminal AND saved to a timestamped
log file under logs/load_bronze/<run_id>/.

Loaders (run in order):
  1. census           — Jurisdictions     → scripts/datasources/census/load_census_gazetteer.py
  2. gsa              — Gov Websites      → scripts/datasources/gsa/load_gsa_domains_to_postgres.py
  3. localview        — Meetings (Old)    → scripts/datasources/localview/load_localview_to_postgres.py
  4. irs              — Non-Profits       → scripts/datasources/irs/load_irs_bmf.py
  5. enrich_ai        — AI Meeting Analysis (Gemini) → packages/llm/src/llm/enrichment/load_enriched_events_ai.py --only analyze
  6. hud_zip_county   — ZIP-County Crosswalk (HUD)   → packages/ingestion/src/ingestion/hud/zip_county.py
  7. shapefiles       — Geometry Shapefiles (Census TIGER) → scripts/datasources/census/load_census_shapefiles.py
  8. place_crosswalks — Place → County / ZCTA Crosswalks  → scripts/datasources/census/load_place_crosswalks.py

Usage:
    python scripts/load_bronze.py                        # run all loaders + dbt bronze
    python scripts/load_bronze.py --retry-failed         # re-run only failed steps from last run
    python scripts/load_bronze.py --retry-run 20260507_082303  # retry a specific run by ID
    python scripts/load_bronze.py --skip localview irs   # skip specific loaders
    python scripts/load_bronze.py --only gsa census      # run specific loaders only
    python scripts/load_bronze.py --truncate             # clear tables before loading
    python scripts/load_bronze.py --dry-run              # parse only, no DB writes
    python scripts/load_bronze.py --no-dbt               # skip the dbt run at the end
"""
import sys
import os
import json
import subprocess
import argparse
import time
import threading
from datetime import datetime
from pathlib import Path

import psycopg2
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils.log_sync import sync_logs, MACHINE_ID


PROJECT_ROOT = Path(__file__).parent.parent
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"
LOG_ROOT = PROJECT_ROOT / "logs" / "load_bronze"

_PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{_PG_PASSWORD}@localhost:5433/open_navigator"

LOADERS = [
    {
        "key": "census",
        "label": "Jurisdictions (Census Gazetteer)",
        "script": "scripts/datasources/census/load_census_gazetteer.py",
        "supports_truncate": False,
        "supports_dry_run": False,
        "tables": [
            "bronze.bronze_jurisdictions_counties",
            "bronze.bronze_jurisdictions_municipalities",
            "bronze.bronze_jurisdictions_school_districts",
            "bronze.bronze_jurisdictions_townships",
            "bronze.bronze_jurisdictions_zcta",
        ],
    },
    {
        "key": "gsa",
        "label": "Gov Websites (GSA Domains)",
        "script": "scripts/datasources/gsa/load_gsa_domains_to_postgres.py",
        "supports_truncate": True,
        "supports_dry_run": True,
        "tables": ["bronze.bronze_gov_domains"],
    },
    {
        "key": "localview",
        "label": "Meetings (LocalView)",
        "script": "scripts/datasources/localview/load_localview_to_postgres.py",
        "supports_truncate": False,
        "supports_dry_run": False,
        "tables": ["bronze.bronze_events_localview"],
    },
    {
        "key": "irs",
        "label": "Non-Profits (IRS BMF)",
        "script": "scripts/datasources/irs/load_irs_bmf.py",
        "supports_truncate": False,
        "supports_dry_run": False,
        "tables": ["bronze.bronze_organizations_nonprofits_irs"],
    },
    {
        "key": "enrich_ai",
        "label": "AI Meeting Analysis (Gemini)",
        "script": "packages/llm/src/llm/enrichment/load_enriched_events_ai.py",
        "extra_args": ["--only", "analyze"],
        "supports_truncate": False,
        "supports_dry_run": True,
        "tables": ["bronze.bronze_events_analysis_ai"],
    },
    {
        "key": "hud_zip_county",
        "label": "ZIP-County Crosswalk (HUD)",
        "script": "packages/ingestion/src/ingestion/hud/zip_county.py",
        "supports_truncate": True,
        "supports_dry_run": True,
        "tables": ["bronze.bronze_jurisdictions_zip_county"],
    },
    {
        "key": "shapefiles",
        "label": "Geometry Shapefiles (Census TIGER)",
        "script": "scripts/datasources/census/load_census_shapefiles.py",
        "supports_truncate": True,
        "supports_dry_run": True,
        "tables": [
            "bronze.bronze_geo_states",
            "bronze.bronze_geo_counties",
            "bronze.bronze_geo_places",
            "bronze.bronze_geo_zcta",
        ],
    },
    {
        # Depends on shapefiles being downloaded (place + county) and on the
        # zcta_place relationship file being downloaded. Computes its own
        # spatial overlay rather than relying on bronze_geo_* tables, so it
        # can run independently of the `shapefiles` step having succeeded.
        "key": "place_crosswalks",
        "label": "Place → County / ZCTA Crosswalks",
        "script": "scripts/datasources/census/load_place_crosswalks.py",
        "supports_truncate": True,
        "supports_dry_run": True,
        "tables": [
            "bronze.bronze_jurisdictions_place_county",
            "bronze.bronze_jurisdictions_place_zcta",
        ],
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
    """
    Return (failed_keys, source_run_id) from a previous run's results.json.
    If run_id is None, uses the most recent run directory.
    Raises FileNotFoundError / ValueError with a descriptive message on bad input.
    """
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
# Database helpers
# ---------------------------------------------------------------------------

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
# Loaders
# ---------------------------------------------------------------------------

def run_loader(loader: dict, truncate: bool, dry_run: bool, log_dir: Path) -> dict:
    tables = loader.get("tables", [])
    before = count_rows(tables)

    cmd = [sys.executable, loader["script"]] + list(loader.get("extra_args", []))
    if truncate and loader["supports_truncate"]:
        cmd.append("--truncate")
    if dry_run and loader["supports_dry_run"]:
        cmd.append("--dry-run")

    log_path = log_dir / f"{loader['key']}.log"
    logger.info(f"$ {' '.join(str(c) for c in cmd)}")
    logger.info(f"  log → {log_path.relative_to(PROJECT_ROOT)}")

    start = time.monotonic()
    exit_code = run_subprocess(cmd, log_path)
    elapsed = time.monotonic() - start

    after = count_rows(tables)

    return {
        "key": loader["key"],
        "label": loader["label"],
        "exit_code": exit_code,
        "elapsed": elapsed,
        "ok": exit_code == 0,
        "truncated": truncate and loader["supports_truncate"],
        "dry_run": dry_run and loader["supports_dry_run"],
        "tables": tables,
        "before": before,
        "after": after,
        "log_path": log_path,
    }


def ensure_dbt_profiles() -> bool:
    if not DBT_PROJECT_DIR.exists():
        return False
    profiles = DBT_PROJECT_DIR / "profiles.yml"
    example = DBT_PROJECT_DIR / "profiles.yml.example"
    if not profiles.exists():
        if example.exists():
            import shutil
            shutil.copy(example, profiles)
            logger.info("Created dbt profiles.yml from example (first-time setup)")
        else:
            logger.warning("dbt profiles.yml and profiles.yml.example both missing")
            return False
    return True


def run_dbt_bronze(select: str, log_dir: Path) -> dict:
    label = f"dbt run --select {select}"
    log_path = log_dir / "dbt.log"

    if not DBT_PROJECT_DIR.exists():
        logger.warning(f"dbt_project/ not found at {DBT_PROJECT_DIR} — skipping")
        return {
            "key": "dbt", "label": label,
            "exit_code": -1, "elapsed": 0.0,
            "ok": False, "skipped": True,
            "tables": [], "log_path": None,
        }

    ensure_dbt_profiles()

    dbt_bin = PROJECT_ROOT / ".venv" / "bin" / "dbt"
    dbt_cmd = str(dbt_bin) if dbt_bin.exists() else "dbt"

    deps_cmd = [dbt_cmd, "deps", "--profiles-dir", str(DBT_PROJECT_DIR)]
    logger.info(f"$ {' '.join(deps_cmd)}")
    run_subprocess(deps_cmd, log_path, cwd=DBT_PROJECT_DIR)

    cmd = [dbt_cmd, "run", "--select", select, "--profiles-dir", str(DBT_PROJECT_DIR)]
    logger.info(f"$ {' '.join(cmd)}")
    logger.info(f"  log → {log_path.relative_to(PROJECT_ROOT)}")

    start = time.monotonic()
    exit_code = run_subprocess(cmd, log_path, cwd=DBT_PROJECT_DIR)
    elapsed = time.monotonic() - start

    return {
        "key": "dbt", "label": label,
        "exit_code": exit_code, "elapsed": elapsed,
        "ok": exit_code == 0, "skipped": False,
        "tables": [], "log_path": log_path,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

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
    logger.info("  BRONZE INGESTION SUMMARY")
    logger.info(f"  Started : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ({fmt_elapsed(duration)} total)")
    logger.info(f"  Logs    : {log_dir.relative_to(PROJECT_ROOT)}/")
    logger.info(thin)
    logger.info(f"  {'STATUS':<10}  {'TIME':>8}  {'ADDED':>12}  {'TOTAL':>12}  LOADER")
    logger.info(thin)

    for r in results:
        if r.get("skipped"):
            tag = "SKIP"
        elif r["ok"]:
            tag = "OK"
        else:
            tag = f"FAIL({r['exit_code']})"

        notes = []
        if r.get("truncated"):
            notes.append("truncated")
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

        tables = r.get("tables", [])
        if len(tables) > 1 and r["ok"]:
            before_map = r.get("before", {})
            after_map = r.get("after", {})
            for tbl in tables:
                b = before_map.get(tbl)
                a = after_map.get(tbl)
                short = tbl.split(".")[-1].replace("bronze_jurisdictions_", "")
                logger.info(
                    f"  {'':10}  {'':8}"
                    f"  {fmt_delta(b, a)}"
                    f"  {fmt_count(a)}"
                    f"    └ {short}"
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
        logger.info(f"  To retry: python scripts/load_bronze.py --retry-failed")
    else:
        logger.success(f"  {summary_line}")
    logger.info(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all bronze data loaders then dbt bronze models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    keys = [l["key"] for l in LOADERS]

    retry_group = parser.add_mutually_exclusive_group()
    retry_group.add_argument(
        "--retry-failed", action="store_true",
        help="Re-run only the steps that failed in the most recent run",
    )
    retry_group.add_argument(
        "--retry-run", metavar="RUN_ID",
        help="Re-run only the steps that failed in a specific run (e.g. 20260507_082303)",
    )

    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument(
        "--skip", nargs="+", choices=keys, metavar="KEY",
        help=f"Loaders to skip. Choices: {', '.join(keys)}",
    )
    filter_group.add_argument(
        "--only", nargs="+", choices=keys, metavar="KEY",
        help="Run only these loaders",
    )

    parser.add_argument(
        "--truncate", action="store_true",
        help="Pass --truncate to loaders that support it",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Pass --dry-run to loaders that support it (no DB writes)",
    )
    parser.add_argument(
        "--no-dbt", action="store_true",
        help="Skip the dbt bronze run at the end",
    )
    parser.add_argument(
        "--dbt-select", default="bronze", metavar="SELECTOR",
        help="dbt node selector (default: 'bronze')",
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
        logger.info(f"Retrying {len(failed_keys)} failed step(s) from run {source_run}: {', '.join(failed_keys)}")

    started_at = datetime.now()
    run_id = started_at.strftime("%Y%m%d_%H%M%S")
    log_dir = LOG_ROOT / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    orchestrator_log = log_dir / "orchestrator.log"
    logger.add(orchestrator_log, level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    logger.info("=" * 80)
    logger.info("  OPEN NAVIGATOR — BRONZE INGESTION")
    logger.info(f"  {started_at.strftime('%Y-%m-%d %H:%M:%S')}  (run: {run_id})  machine: {MACHINE_ID}")
    logger.info("=" * 80)

    # Determine which loaders to run (retry takes priority over --skip/--only)
    active_keys = retry_only or None
    loaders = list(LOADERS)
    if active_keys is not None:
        loaders = [l for l in loaders if l["key"] in active_keys]
    elif args.only:
        loaders = [l for l in loaders if l["key"] in args.only]
    elif args.skip:
        loaders = [l for l in loaders if l["key"] not in args.skip]

    run_dbt = "dbt" in (active_keys or []) or (
        not args.no_dbt and not args.dry_run and active_keys is None
    )

    if args.truncate:
        logger.warning("--truncate active: supported tables will be cleared before loading")
    if args.dry_run:
        logger.warning("--dry-run active: no data will be written to the database")

    results: list[dict] = []

    def checkpoint() -> None:
        save_results(results, log_dir, started_at)
        sync_logs(log_dir, run_type="load_bronze", project_root=PROJECT_ROOT)

    for loader in loaders:
        logger.info("")
        logger.info(f"  {'─' * 76}")
        logger.info(f"  ▶  {loader['label']}")
        logger.info(f"  {'─' * 76}")
        result = run_loader(loader, truncate=args.truncate, dry_run=args.dry_run, log_dir=log_dir)
        results.append(result)
        if not result["ok"]:
            logger.error(f"  Loader exited with code {result['exit_code']} — continuing to next step")
        checkpoint()

    if run_dbt:
        logger.info("")
        logger.info(f"  {'─' * 76}")
        logger.info(f"  ▶  dbt run --select {args.dbt_select}")
        logger.info(f"  {'─' * 76}")
        results.append(run_dbt_bronze(select=args.dbt_select, log_dir=log_dir))
        checkpoint()

    print_summary(results, started_at, log_dir)

    failed = [r for r in results if not r["ok"] and not r.get("skipped")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
