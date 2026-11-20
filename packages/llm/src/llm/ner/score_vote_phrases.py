"""CLI: score bronze vote-phrase hits against Gemini Part 1 media anchors."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from loguru import logger

from core_lib.paths import repo_root
from llm.ner.score import load_gemini_anchors, load_hits_by_video, score_anchors
from llm.ner.store import TABLE, ensure_table, table_stats


def _resolve_database_url(args: argparse.Namespace) -> str | None:
    return (args.database_url or os.environ.get("OPEN_NAVIGATOR_DATABASE_URL") or "").strip() or None


def _misses_output_path(utc_run_id: str) -> Path:
    return (
        repo_root(__file__)
        / "data"
        / "cache"
        / "vote_phrase_score"
        / utc_run_id
        / "misses.jsonl"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score vote-phrase bronze hits against Gemini media anchors.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres URL (default: OPEN_NAVIGATOR_DATABASE_URL)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max anchor rows to score")
    args = parser.parse_args(argv)

    database_url = _resolve_database_url(args)
    if not database_url:
        logger.error("Set --database-url or OPEN_NAVIGATOR_DATABASE_URL")
        return 1

    conn = psycopg2.connect(database_url)
    try:
        ensure_table(conn)
        stats = table_stats(conn)
    finally:
        conn.close()

    if stats["row_count"] == 0:
        logger.error(
            "{} is empty — run spot_vote_phrases first (without --dry-run) to load hits.",
            TABLE,
        )
        print(f"{TABLE} has 0 rows; nothing to score.")
        return 1

    anchors = load_gemini_anchors(database_url, limit=args.limit)
    if not anchors:
        logger.warning("No Gemini media anchors found for Part 1 decision videos")
        print("anchors=0 hits_table_rows={}".format(stats["row_count"]))
        return 0

    video_ids = {a["video_id"] for a in anchors}
    hits_by_video = load_hits_by_video(database_url, video_ids)

    result = score_anchors(anchors, hits_by_video, window=60.0)
    missed = result["decisions_missed"]

    utc_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = _misses_output_path(utc_run_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in missed:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Wrote {} miss record(s) to {}", len(missed), out_path)

    summary = (
        f"decisions_with_anchor={result['decisions_with_anchor']} "
        f"decisions_hit={result['decisions_hit']} "
        f"decisions_missed={len(missed)} "
        f"hits_table_rows={stats['row_count']} "
        f"misses_jsonl={out_path}"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())