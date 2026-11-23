#!/usr/bin/env python3
"""
Reclassify pre-split deep Part 1 stamps onto ``policy_*_full_*`` columns (#766).

After #755, light stamps reuse ``policy_analysis_at`` / ``policy_report_at`` and
full writes ``policy_*_full_*``. Historical deep analyses
(``prompts/policy_analysis_part_1.md``) were never moved, so Analysis light % on
the batch dashboard is mostly old full/deep coverage while Analysis full stays 0.

This CLI reads each stamped analysis path's sibling ``*.meta.json``, classifies
``prompt_name`` / ``prompt_file``, and (with ``--apply``) moves part_1 stamps to
the full columns. Lite stays on light. Unknown metas are left unchanged.

Usage::

    python -m llm.gemini.reclassify_policy_tier_stamps --dry-run
    python -m llm.gemini.reclassify_policy_tier_stamps --apply --limit 500
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.gemini.persist_policy_analysis_bronze import database_url  # noqa: E402
from llm.gemini.transcript_cache_paths import (  # noqa: E402
    meta_path_for_analysis,
    report_path_for_analysis,
)

# Deep Part 1 prompt used before the light/full split (#755 / #766).
_FULL_PROMPT_NAMES = frozenset(
    {
        "policy_analysis_part_1",
        "policy_analysis_part1",
    }
)
_LIGHT_PROMPT_NAMES = frozenset(
    {
        "policy_analysis_lite",
        "policy_analysis_light",
    }
)


@dataclass
class ReclassStats:
    scanned: int = 0
    missing_path: int = 0
    missing_meta: int = 0
    unknown_prompt: int = 0
    already_full: int = 0
    keep_light: int = 0
    move_analysis: int = 0
    move_report: int = 0
    applied: int = 0
    errors: int = 0
    samples: List[str] = field(default_factory=list)


def classify_prompt_meta(meta: Dict[str, Any]) -> Optional[str]:
    """Return ``full``, ``light``, or ``None`` (unknown / leave alone)."""
    name = str(meta.get("prompt_name") or "").strip().lower()
    prompt_file = str(meta.get("prompt_file") or meta.get("prompt_path") or "").replace(
        "\\", "/"
    )
    stem = Path(prompt_file).stem.lower() if prompt_file else ""
    tier = str(meta.get("analysis_tier") or "").strip().lower()
    if tier in ("full", "light"):
        return tier
    for candidate in (name, stem):
        if candidate in _FULL_PROMPT_NAMES or candidate.endswith("part_1"):
            return "full"
        if candidate in _LIGHT_PROMPT_NAMES or "lite" in candidate:
            return "light"
    if "policy_analysis_part_1" in prompt_file or "part_1.md" in prompt_file:
        return "full"
    if "policy_analysis_lite" in prompt_file or "lite.md" in prompt_file:
        return "light"
    return None


def _abs_repo_path(rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p
    return _REPO_ROOT / p


def _load_meta(analysis_path: Path) -> Optional[Dict[str, Any]]:
    meta_path = meta_path_for_analysis(analysis_path)
    if not meta_path.is_file():
        # Older layouts sometimes drop .meta next to the JSON.
        alt = analysis_path.with_suffix(".meta.json")
        if alt.is_file():
            meta_path = alt
        else:
            return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("unreadable meta {}: {}", meta_path, exc)
        return None
    return data if isinstance(data, dict) else None


def _fetch_candidates(
    conn: Any, *, limit: Optional[int]
) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """video_id, analysis_path, report_path for light-stamped rows without full analysis."""
    sql = """
        SELECT video_id, policy_analysis_path, policy_report_path
        FROM bronze.bronze_event_youtube
        WHERE policy_analysis_at IS NOT NULL
          AND policy_analysis_full_at IS NULL
          AND policy_analysis_path IS NOT NULL
          AND btrim(policy_analysis_path) <> ''
        ORDER BY policy_analysis_at ASC NULLS LAST
    """
    params: Tuple[Any, ...] = ()
    if limit is not None and limit > 0:
        sql += " LIMIT %s"
        params = (int(limit),)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [(str(r[0]), r[1], r[2]) for r in cur.fetchall()]


def _apply_move(
    conn: Any,
    *,
    video_id: str,
    move_report: bool,
) -> None:
    """Copy light stamps onto full columns and clear light success stamps."""
    with conn.cursor() as cur:
        if move_report:
            cur.execute(
                """
                UPDATE bronze.bronze_event_youtube
                SET
                  policy_analysis_full_at = policy_analysis_at,
                  policy_analysis_full_path = policy_analysis_path,
                  policy_analysis_full_error = policy_analysis_error,
                  policy_report_full_at = policy_report_at,
                  policy_report_full_path = policy_report_path,
                  policy_report_full_error = policy_report_error,
                  policy_analysis_at = NULL,
                  policy_analysis_path = NULL,
                  policy_analysis_error = NULL,
                  policy_report_at = NULL,
                  policy_report_path = NULL,
                  policy_report_error = NULL,
                  last_updated = CURRENT_TIMESTAMP
                WHERE video_id = %s
                  AND policy_analysis_at IS NOT NULL
                  AND policy_analysis_full_at IS NULL
                """,
                (video_id,),
            )
        else:
            cur.execute(
                """
                UPDATE bronze.bronze_event_youtube
                SET
                  policy_analysis_full_at = policy_analysis_at,
                  policy_analysis_full_path = policy_analysis_path,
                  policy_analysis_full_error = policy_analysis_error,
                  policy_analysis_at = NULL,
                  policy_analysis_path = NULL,
                  policy_analysis_error = NULL,
                  last_updated = CURRENT_TIMESTAMP
                WHERE video_id = %s
                  AND policy_analysis_at IS NOT NULL
                  AND policy_analysis_full_at IS NULL
                """,
                (video_id,),
            )


def reclassify_policy_tier_stamps(
    *,
    apply: bool = False,
    limit: Optional[int] = None,
    database_url_override: Optional[str] = None,
) -> ReclassStats:
    import psycopg2

    stats = ReclassStats()
    conn = psycopg2.connect(database_url(database_url_override))
    try:
        rows = _fetch_candidates(conn, limit=limit)
        logger.info(
            "Candidates (light stamp, no full stamp): {:,}{}",
            len(rows),
            f" (limit={limit})" if limit else "",
        )
        for video_id, analysis_rel, report_rel in rows:
            stats.scanned += 1
            if not analysis_rel:
                stats.missing_path += 1
                continue
            analysis_path = _abs_repo_path(str(analysis_rel))
            # Filename already marks full-tier artifacts (#755).
            if analysis_path.stem.endswith("_full"):
                tier = "full"
                meta: Optional[Dict[str, Any]] = {"prompt_name": "policy_analysis_part_1"}
            else:
                meta = _load_meta(analysis_path)
                if meta is None:
                    stats.missing_meta += 1
                    continue
                tier = classify_prompt_meta(meta)
            if tier is None:
                stats.unknown_prompt += 1
                if len(stats.samples) < 8:
                    stats.samples.append(
                        f"{video_id}: unknown prompt_name="
                        f"{meta.get('prompt_name')!r} file={meta.get('prompt_file')!r}"
                    )
                continue
            if tier == "light":
                stats.keep_light += 1
                continue
            # tier == full → move
            move_report = False
            if report_rel:
                # Prefer moving the paired report when the sibling md exists or
                # the bronze report path matches the analysis stem.
                expected = report_path_for_analysis(analysis_path)
                report_path = _abs_repo_path(str(report_rel))
                if report_path.is_file() or expected.is_file():
                    move_report = True
                elif Path(str(report_rel)).stem.replace("_full", "") == analysis_path.stem:
                    move_report = True
            stats.move_analysis += 1
            if move_report:
                stats.move_report += 1
            if len(stats.samples) < 8:
                stats.samples.append(
                    f"{video_id}: move analysis→full"
                    + (" + report→full" if move_report else "")
                    + f" path={analysis_rel}"
                )
            if apply:
                try:
                    _apply_move(conn, video_id=video_id, move_report=move_report)
                    stats.applied += 1
                except Exception as exc:
                    conn.rollback()
                    stats.errors += 1
                    logger.warning("apply failed for {}: {}", video_id, exc)
                    continue
        if apply:
            conn.commit()
            logger.success("Applied {:,} reclassifications", stats.applied)
        else:
            logger.info("Dry-run only — pass --apply to write stamps")
    finally:
        conn.close()
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move pre-split Part 1 bronze stamps onto policy_*_full_* (#766)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write UPDATEs (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run (default)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max candidate rows to scan",
    )
    args = parser.parse_args(argv)
    apply = bool(args.apply) and not args.dry_run
    stats = reclassify_policy_tier_stamps(apply=apply, limit=args.limit)
    logger.info(
        "scanned={:,} keep_light={:,} move_analysis={:,} move_report={:,} "
        "missing_meta={:,} unknown={:,} missing_path={:,} applied={:,} errors={:,}",
        stats.scanned,
        stats.keep_light,
        stats.move_analysis,
        stats.move_report,
        stats.missing_meta,
        stats.unknown_prompt,
        stats.missing_path,
        stats.applied,
        stats.errors,
    )
    for sample in stats.samples:
        logger.info("  sample: {}", sample)
    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
