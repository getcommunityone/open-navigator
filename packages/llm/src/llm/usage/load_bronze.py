"""Load the usage logs into Postgres (#262).

    python -m llm.usage.load_bronze                 # every file under the log directory
    python -m llm.usage.load_bronze --dry-run       # count rows, write nothing

Reads ``llm_calls_*.jsonl`` into ``bronze.bronze_llm_call`` and
``gpu_runs_*.jsonl`` into ``bronze.bronze_gpu_run`` (migration 111, applied if
the tables are missing). Rows are keyed by their id, so a re-run adds only what
is new.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from loguru import logger

from llm.usage.calls import usage_log_dir

MIGRATION = "111_create_bronze_llm_usage.sql"

LLM_CALL_COLUMNS = (
    "llm_call_id", "called_at", "provider", "model", "api_mode", "stage", "video_id",
    "jurisdiction_id", "run_id", "input_token_count", "cached_input_token_count",
    "output_token_count", "thinking_token_count", "total_token_count", "latency_seconds",
    "attempt_count", "is_ok", "error_type", "host_name",
)  # fmt: skip
GPU_RUN_COLUMNS = (
    "gpu_run_id", "step_name", "started_at", "ended_at", "wall_seconds", "gpu_count",
    "gpu_name", "gpu_hours", "gpu_sample_count", "avg_gpu_utilization_pct",
    "max_gpu_memory_used_mb", "energy_wh", "video_id", "jurisdiction_id", "run_id",
    "host_name",
)  # fmt: skip

TABLES = {
    "llm_calls": ("bronze.bronze_llm_call", LLM_CALL_COLUMNS),
    "gpu_runs": ("bronze.bronze_gpu_run", GPU_RUN_COLUMNS),
}


def read_rows(log_dir: Path, prefix: str) -> Iterator[dict[str, Any]]:
    """Every JSON object in ``<prefix>_*.jsonl``; a line that isn't one is skipped."""
    for path in sorted(Path(log_dir).glob(f"{prefix}_*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for number, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("{}:{} is not JSON, skipped", path.name, number)
                    continue
                if isinstance(row, dict):
                    yield row


def to_tuples(rows: Iterable[dict[str, Any]], columns: Sequence[str]) -> list[tuple]:
    """Rows as tuples in column order; a row with no id (the first column) is dropped."""
    return [tuple(r.get(c) for c in columns) for r in rows if r.get(columns[0])]


def insert_sql(table: str, columns: Sequence[str]) -> str:
    return (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({columns[0]}) DO NOTHING RETURNING 1"
    )


def load(log_dir: Path, *, database_url: str | None = None, dry_run: bool = False) -> dict[str, int]:
    """Load both logs. Returns rows read per log, and rows inserted unless ``dry_run``."""
    counts: dict[str, int] = {}
    batches = {
        prefix: to_tuples(read_rows(log_dir, prefix), columns)
        for prefix, (_, columns) in TABLES.items()
    }
    for prefix, values in batches.items():
        counts[f"{prefix}_read"] = len(values)
    if dry_run:
        return counts

    import psycopg2
    from psycopg2.extras import execute_values

    from llm.gemini.persist_policy_analysis_bronze import (
        _MIGRATIONS_DIR,
        _apply_migration,
    )
    from llm.gemini.persist_policy_analysis_bronze import database_url as resolve_url

    if not (_MIGRATIONS_DIR / MIGRATION).is_file():
        # _apply_migration only warns about a missing file; the insert would then fail
        # with a vaguer "relation does not exist".
        raise SystemExit(f"Migration not found: {_MIGRATIONS_DIR / MIGRATION} (run from a repository checkout)")

    conn = psycopg2.connect(resolve_url(database_url))
    try:
        _apply_migration(conn, MIGRATION)
        with conn.cursor() as cur:
            for prefix, (table, columns) in TABLES.items():
                inserted = 0
                if batches[prefix]:
                    inserted = len(
                        execute_values(
                            cur,
                            insert_sql(table, columns),
                            batches[prefix],
                            page_size=500,
                            fetch=True,
                        )
                    )
                counts[f"{prefix}_inserted"] = inserted
        conn.commit()
    finally:
        conn.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--log-dir", default=None, help="Usage log directory (default: LLM_USAGE_LOG_DIR)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Count rows and write nothing")
    args = parser.parse_args()
    log_dir = Path(args.log_dir).expanduser() if args.log_dir else usage_log_dir()
    counts = load(log_dir, database_url=args.database_url, dry_run=args.dry_run)
    for name, value in counts.items():
        logger.info("{}: {:,}", name, value)
    logger.success("Usage logs {} from {}", "counted" if args.dry_run else "loaded", log_dir)


if __name__ == "__main__":
    main()
