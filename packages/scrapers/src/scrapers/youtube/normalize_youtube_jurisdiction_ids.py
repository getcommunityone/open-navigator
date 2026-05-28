#!/usr/bin/env python3
"""
Normalize legacy numeric ``jurisdiction_id`` values to canonical ``{type}_{geoid}`` ids.

Legacy YouTube rows use ``jurisdiction.id`` (e.g. ``368`` = Andalusia).
Canonical ids match ``intermediate.int_jurisdictions`` (e.g. ``municipality_0101708``).

Updates ``bronze.bronze_events_youtube`` and renames ``data/cache/gemini_transcript_policy`` folders.

Usage (repo root)::

    .venv/bin/python packages/scrapers/src/scrapers/youtube/normalize_youtube_jurisdiction_ids.py --dry-run
    .venv/bin/python packages/scrapers/src/scrapers/youtube/normalize_youtube_jurisdiction_ids.py
    .venv/bin/python packages/scrapers/src/scrapers/youtube/normalize_youtube_jurisdiction_ids.py --cache-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discovery.jurisdiction_discovery_pipeline import jurisdiction_pk_from_geoid  # noqa: E402
from scripts.gemini.transcript_cache_paths import (  # noqa: E402
    _CACHE_TYPE_FROM_TYPED_ID,
    cache_type_segment,
    jurisdiction_cache_folder_name,
    jurisdiction_geo_dir,
)

_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
_NUMERIC_JID_RE = re.compile(r"^[0-9]+$")
_TYPED_JID_RE = re.compile(
    r"^(?P<jtype>county|municipality|state|township|school_district)_(?P<geoid>.+)$"
)


def _database_url(explicit: Optional[str]) -> str:
    load_dotenv(_REPO_ROOT / ".env")
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


def _normalize_place_name(name: str) -> str:
    n = (name or "").strip().lower()
    for suffix in (" city", " town", " village", " county", " ccd"):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return re.sub(r"\s+", " ", n).strip()


def _names_compatible(youtube_name: str, search_name: str) -> bool:
    """Reject ``jurisdiction.id`` collisions (same id, different place)."""
    a = _normalize_place_name(youtube_name)
    b = _normalize_place_name(search_name)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    return len(a_tokens & b_tokens) >= max(1, min(len(a_tokens), len(b_tokens)) // 2)


def _infer_jtype_from_label(name: str, search_type: Optional[str]) -> str:
    blob = f"{name or ''} {search_type or ''}".lower()
    if "school" in blob and "district" in blob:
        return "school_district"
    if "county" in blob and "city" not in blob.split("county")[0][-5:]:
        if "county" in (name or "").lower():
            return "county"
    st = (search_type or "").lower()
    if st in ("county", "school_district", "school", "township", "state"):
        return "school_district" if st == "school" else st
    return "city"


def _canonical_from_search_row(
    geoid: Optional[str],
    search_type: Optional[str],
    jurisdiction_name: str,
) -> str:
    jt = _infer_jtype_from_label(jurisdiction_name, search_type)
    return jurisdiction_pk_from_geoid(geoid, jt, name=jurisdiction_name)


def build_legacy_to_canonical_map(conn) -> Dict[str, str]:
    """``legacy_id`` → ``canonical_id`` for rows that need normalization."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    mapping: Dict[str, str] = {}
    skipped: Dict[str, str] = {}

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT DISTINCT
                y.jurisdiction_id AS legacy_id,
                y.jurisdiction_name,
                y.state_code,
                js.name AS search_name,
                js.state AS search_state,
                js.geoid AS search_geoid,
                js.type AS search_type
            FROM bronze.bronze_events_youtube y
            LEFT JOIN public.jurisdiction js
              ON js.id::text = y.jurisdiction_id
            WHERE y.jurisdiction_id ~ '^[0-9]+$'
            """
        )
        rows = cur.fetchall()

        for row in rows:
            legacy = str(row["legacy_id"] or "").strip()
            if not legacy or legacy in mapping:
                continue
            name = str(row["jurisdiction_name"] or "").strip()
            state = str(row["state_code"] or "").strip().upper()
            geoid = row.get("search_geoid")
            stype = row.get("search_type")
            search_name = str(row.get("search_name") or "").strip()
            search_state = str(row.get("search_state") or "").strip().upper()

            canonical = ""
            if (
                geoid
                and str(geoid).strip()
                and search_name
                and _names_compatible(name, search_name)
                and (not search_state or not state or search_state == state)
            ):
                canonical = _canonical_from_search_row(str(geoid), stype, name)

            if not canonical and name and state:
                cur.execute(
                    """
                    SELECT jurisdiction_id, jurisdiction_type, name
                    FROM intermediate.int_jurisdictions
                    WHERE state_code = %s
                      AND jurisdiction_type IN (
                          'municipality', 'county', 'school_district'
                      )
                    """,
                    (state,),
                )
                want = _normalize_place_name(name)
                hits = []
                for j in cur.fetchall():
                    jname = _normalize_place_name(str(j["name"] or ""))
                    if jname == want or jname.startswith(want + " ") or want.startswith(jname + " "):
                        hits.append(str(j["jurisdiction_id"]))
                hits = list(dict.fromkeys(hits))
                if len(hits) == 1:
                    canonical = hits[0]

            if canonical and canonical != legacy:
                mapping[legacy] = canonical
            else:
                skipped[legacy] = name or "(no name)"

    if skipped:
        logger.warning(
            "Skipped {} legacy id(s) without a confident canonical match (first 10): {}",
            len(skipped),
            list(skipped.items())[:10],
        )
    logger.info("Resolved {} legacy → canonical mapping(s)", len(mapping))
    return mapping


def update_bronze_jurisdiction_ids(
    conn,
    mapping: Dict[str, str],
    *,
    dry_run: bool,
) -> Dict[str, int]:
    stats: Dict[str, int] = defaultdict(int)
    if not mapping:
        return dict(stats)

    import psycopg2

    with conn.cursor() as cur:
        for legacy, canonical in sorted(mapping.items()):
            cur.execute(
                """
                UPDATE bronze.bronze_events_youtube
                SET jurisdiction_id = %s
                WHERE jurisdiction_id = %s
                """,
                (canonical, legacy),
            )
            n = cur.rowcount
            stats["youtube_rows"] += n
            if n:
                logger.info("bronze youtube: {} → {} ({} row(s))", legacy, canonical, n)

        for legacy, canonical in sorted(mapping.items()):
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'bronze'
                  AND table_name = 'bronze_events_channels'
                  AND column_name = 'jurisdiction_id'
                LIMIT 1
                """
            )
            if not cur.fetchone():
                break
            cur.execute(
                """
                UPDATE bronze.bronze_events_channels
                SET jurisdiction_id = %s
                WHERE jurisdiction_id = %s
                """,
                (canonical, legacy),
            )
            if cur.rowcount:
                stats["channel_rows"] += cur.rowcount
                logger.info(
                    "bronze channels: {} → {} ({} row(s))",
                    legacy,
                    canonical,
                    cur.rowcount,
                )

        if not dry_run:
            conn.commit()
        else:
            conn.rollback()
            stats["dry_run"] = 1

    return dict(stats)


def _cache_type_for_canonical(canonical_id: str) -> str:
    match = _TYPED_JID_RE.match(canonical_id)
    if match:
        return _CACHE_TYPE_FROM_TYPED_ID.get(match.group("jtype"), match.group("jtype"))
    return "municipality"


def _merge_dir_contents(src: Path, dest: Path, *, dry_run: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dest / child.name
        if child.is_dir():
            if target.exists():
                _merge_dir_contents(child, target, dry_run=dry_run)
                if not dry_run and not any(child.iterdir()):
                    child.rmdir()
            elif dry_run:
                logger.info("would merge dir: {} → {}", child, target)
            else:
                shutil.move(str(child), str(target))
        elif target.exists():
            logger.warning("skip file (dest exists): {}", target)
        elif dry_run:
            logger.info("would move file: {} → {}", child, target)
        else:
            shutil.move(str(child), str(target))


def migrate_policy_cache_ids(
    cache_dir: Path,
    mapping: Dict[str, str],
    *,
    dry_run: bool,
) -> Dict[str, int]:
    cache_dir = cache_dir.resolve()
    stats: Dict[str, int] = defaultdict(int)

    for legacy, canonical in sorted(mapping.items()):
        if legacy == canonical:
            continue
        segment = cache_type_segment(canonical)
        dest_folder = jurisdiction_cache_folder_name(canonical)
        dest_paths: list[Path] = []

        for geo in list(cache_dir.glob("*/" + segment + "/" + legacy)):
            if not geo.is_dir():
                continue
            dest_geo = geo.parent / dest_folder
            if dest_geo.resolve() == geo.resolve():
                stats["already_named"] += 1
                dest_paths.append(dest_geo)
                continue
            if dest_geo.exists():
                if dry_run:
                    logger.info("would merge {} → {}", geo, dest_geo)
                    stats["would_merge"] += 1
                else:
                    _merge_dir_contents(geo, dest_geo, dry_run=False)
                    if not any(geo.iterdir()):
                        geo.rmdir()
                    stats["merged"] += 1
            elif dry_run:
                logger.info("would rename {} → {}", geo, dest_geo)
                stats["would_rename"] += 1
            else:
                shutil.move(str(geo), str(dest_geo))
                stats["renamed"] += 1
            dest_paths.append(dest_geo)

        flat = cache_dir / legacy
        if flat.is_dir():
            st = ""
            if canonical.startswith("municipality_"):
                for geo_path in dest_paths:
                    if geo_path.parent.parent.parent.name:
                        st = geo_path.parent.parent.parent.name
                        break
            dest_geo = jurisdiction_geo_dir(
                cache_dir, canonical, state_code=st or None
            )
            if dry_run:
                logger.info("would move flat {} → {}", flat, dest_geo)
                stats["would_move_flat"] += 1
            elif dest_geo.exists():
                _merge_dir_contents(flat, dest_geo, dry_run=False)
                if not any(flat.iterdir()):
                    flat.rmdir()
                stats["merged_flat"] += 1
            else:
                dest_geo.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(flat), str(dest_geo))
                stats["moved_flat"] += 1
            dest_paths.append(dest_geo)

        for dest in dest_paths:
            if dest.is_dir():
                _patch_cache_json_jurisdiction_id(dest, canonical, dry_run=dry_run)

    return dict(stats)


def _patch_cache_json_jurisdiction_id(
    root: Path,
    canonical: str,
    *,
    dry_run: bool,
) -> None:
    if not root.is_dir():
        return
    for path in root.rglob("*.json"):
        if path.parent.name not in (
            "01_transcripts",
            "02_analysis",
            "04_runs",
        ) and "_transcript" not in path.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("jurisdiction_id") or "") == canonical:
            continue
        data["jurisdiction_id"] = canonical
        if not dry_run:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Rename cache folders only (bronze already updated)",
    )
    parser.add_argument(
        "--bronze-only",
        action="store_true",
        help="Update bronze only (no cache moves)",
    )
    args = parser.parse_args()

    db_url = _database_url(args.database_url or None)
    if not db_url:
        raise SystemExit("Set DATABASE_URL or NEON_DATABASE_URL_DEV")

    import psycopg2

    with psycopg2.connect(db_url) as conn:
        mapping = build_legacy_to_canonical_map(conn)
        if args.dry_run:
            for legacy, canonical in sorted(mapping.items())[:20]:
                logger.info("map: {} → {}", legacy, canonical)
            if len(mapping) > 20:
                logger.info("… and {} more", len(mapping) - 20)
        if not args.cache_only:
            bstats = update_bronze_jurisdiction_ids(conn, mapping, dry_run=args.dry_run)
            for k, v in sorted(bstats.items()):
                logger.info("bronze {}: {}", k, v)

    if not args.bronze_only and mapping:
        cstats = migrate_policy_cache_ids(
            Path(args.cache_dir), mapping, dry_run=args.dry_run
        )
        for k, v in sorted(cstats.items()):
            logger.info("cache {}: {}", k, v)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
