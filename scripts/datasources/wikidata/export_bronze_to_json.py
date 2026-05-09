#!/usr/bin/env python3
"""
Export bronze jurisdiction tables to a local JSON cache for offline use in Google Colab.

Connects to Postgres once, dumps the four bronze base tables for the requested states,
writes a single JSON file locally, then optionally copies it to Google Drive.

Drive sync uses the same mount-first / rclone-fallback approach as scripts/utils/log_sync.py:
  1. Filesystem copy to the mounted Drive path (preferred on WSL2/Windows with Google Drive Desktop)
  2. rclone upload (for Linux servers without a mounted Drive)

Configuration (env vars — all optional):
  LOG_GDRIVE_MOUNT        Path to mounted Google Drive root (default: /mnt/g/My Drive)
  WIKIDATA_GDRIVE_BASE    Sub-path inside the mount (default: CommunityOne/wikidata)
  RCLONE_GDRIVE_REMOTE    rclone remote name used as fallback (default: gdrive)

Usage:
    # Export priority states (default) — local only
    .venv/bin/python scripts/datasources/wikidata/export_bronze_to_json.py

    # Export specific states
    .venv/bin/python scripts/datasources/wikidata/export_bronze_to_json.py --states AL,GA,IN

    # Export and sync to Google Drive
    .venv/bin/python scripts/datasources/wikidata/export_bronze_to_json.py --sync-to-drive

    # Custom Drive sub-path
    WIKIDATA_GDRIVE_BASE="MyProject/wikidata" \\
        .venv/bin/python scripts/datasources/wikidata/export_bronze_to_json.py --sync-to-drive

The JSON produced can be consumed by load_jurisdictions_wikidata.py via --json-cache-dir:
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py \\
        --json-cache-dir data/cache/wikidata --states AL,GA
"""
import os
import sys
import argparse
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

try:
    import psycopg2
except ModuleNotFoundError:
    _repo_root = Path(__file__).resolve().parents[3]
    _venv_py = _repo_root / ".venv" / "bin" / "python"
    sys.stderr.write(
        "ModuleNotFoundError: psycopg2 — install deps in the project venv.\n"
        f"  Setup: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\n"
        f"  Then: {_venv_py} {__file__} ...\n"
    )
    sys.exit(1)

from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Drive config — mirrors log_sync.py conventions
# ---------------------------------------------------------------------------
GDRIVE_MOUNT = Path(os.getenv("LOG_GDRIVE_MOUNT", "/mnt/g/My Drive"))
WIKIDATA_GDRIVE_BASE = os.getenv("WIKIDATA_GDRIVE_BASE", "CommunityOne/wikidata")
RCLONE_REMOTE = os.getenv("RCLONE_GDRIVE_REMOTE", "gdrive")

# ---------------------------------------------------------------------------
# State map
# ---------------------------------------------------------------------------
PRIORITY_STATES = ["AL", "GA", "IN", "MA", "WA", "WI"]

STATE_NAMES: Dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


# ---------------------------------------------------------------------------
# Bronze table queries
# ---------------------------------------------------------------------------

def _export_municipalities(conn, states: List[str]) -> Dict[str, List[Dict]]:
    cur = conn.cursor()
    result: Dict[str, List[Dict]] = {s: [] for s in states}
    try:
        placeholders = ",".join(["%s"] * len(states))
        cur.execute(
            f"""
            SELECT usps, geoid, ansicode, name, lsad, funcstat,
                   aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date
            FROM bronze.bronze_jurisdictions_municipalities
            WHERE usps IN ({placeholders})
            ORDER BY usps, geoid
            """,
            states,
        )
        for row in cur.fetchall():
            (usps, geoid, ansicode, name, lsad, funcstat,
             aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date) = row
            us = str(usps or "").strip().upper()
            if us not in result:
                continue
            result[us].append({
                "geoid": str(geoid or "").strip().replace("-", ""),
                "ansicode": str(ansicode).strip() if ansicode else None,
                "name": str(name).strip() if name else None,
                "lsad": str(lsad).strip() if lsad else None,
                "funcstat": str(funcstat).strip() if funcstat else None,
                "aland": float(aland) if aland is not None else None,
                "awater": float(awater) if awater is not None else None,
                "aland_sqmi": float(aland_sqmi) if aland_sqmi is not None else None,
                "awater_sqmi": float(awater_sqmi) if awater_sqmi is not None else None,
                "intptlat": str(intptlat).strip() if intptlat else None,
                "intptlong": str(intptlong).strip() if intptlong else None,
                "ingestion_date": str(ingestion_date) if ingestion_date else None,
            })
    finally:
        cur.close()
    return result


def _export_counties(conn, states: List[str]) -> Dict[str, List[Dict]]:
    cur = conn.cursor()
    result: Dict[str, List[Dict]] = {s: [] for s in states}
    try:
        placeholders = ",".join(["%s"] * len(states))
        cur.execute(
            f"""
            SELECT usps, geoid, ansicode, name,
                   aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date
            FROM bronze.bronze_jurisdictions_counties
            WHERE usps IN ({placeholders})
            ORDER BY usps, geoid
            """,
            states,
        )
        for row in cur.fetchall():
            (usps, geoid, ansicode, name,
             aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date) = row
            us = str(usps or "").strip().upper()
            if us not in result:
                continue
            result[us].append({
                "geoid": str(geoid or "").strip().replace("-", ""),
                "ansicode": str(ansicode).strip() if ansicode else None,
                "name": str(name).strip() if name else None,
                "aland": float(aland) if aland is not None else None,
                "awater": float(awater) if awater is not None else None,
                "aland_sqmi": float(aland_sqmi) if aland_sqmi is not None else None,
                "awater_sqmi": float(awater_sqmi) if awater_sqmi is not None else None,
                "intptlat": str(intptlat).strip() if intptlat else None,
                "intptlong": str(intptlong).strip() if intptlong else None,
                "ingestion_date": str(ingestion_date) if ingestion_date else None,
            })
    finally:
        cur.close()
    return result


def _export_school_districts(conn, states: List[str]) -> Dict[str, List[Dict]]:
    cur = conn.cursor()
    result: Dict[str, List[Dict]] = {s: [] for s in states}
    try:
        placeholders = ",".join(["%s"] * len(states))
        cur.execute(
            f"""
            SELECT usps, geoid, name, lograde, higrade,
                   aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date
            FROM bronze.bronze_jurisdictions_school_districts
            WHERE usps IN ({placeholders})
            ORDER BY usps, geoid
            """,
            states,
        )
        for row in cur.fetchall():
            (usps, geoid, name, lograde, higrade,
             aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date) = row
            us = str(usps or "").strip().upper()
            if us not in result:
                continue
            result[us].append({
                "geoid": str(geoid or "").strip().replace("-", ""),
                "name": str(name).strip() if name else None,
                "lograde": str(lograde).strip() if lograde else None,
                "higrade": str(higrade).strip() if higrade else None,
                "aland": float(aland) if aland is not None else None,
                "awater": float(awater) if awater is not None else None,
                "aland_sqmi": float(aland_sqmi) if aland_sqmi is not None else None,
                "awater_sqmi": float(awater_sqmi) if awater_sqmi is not None else None,
                "intptlat": str(intptlat).strip() if intptlat else None,
                "intptlong": str(intptlong).strip() if intptlong else None,
                "ingestion_date": str(ingestion_date) if ingestion_date else None,
            })
    finally:
        cur.close()
    return result


def _export_states_table(conn, states: List[str]) -> Dict[str, List[Dict]]:
    cur = conn.cursor()
    result: Dict[str, List[Dict]] = {s: [] for s in states}
    try:
        placeholders = ",".join(["%s"] * len(states))
        cur.execute(
            f"""
            SELECT usps, geoid, ansicode, name,
                   aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date
            FROM bronze.bronze_jurisdictions_states
            WHERE usps IN ({placeholders})
            ORDER BY usps, geoid
            """,
            states,
        )
        for row in cur.fetchall():
            (usps, geoid, ansicode, name,
             aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date) = row
            us = str(usps or "").strip().upper()
            if us not in result:
                continue
            result[us].append({
                "geoid": str(geoid or "").strip().replace("-", ""),
                "ansicode": str(ansicode).strip() if ansicode else None,
                "name": str(name).strip() if name else None,
                "aland": float(aland) if aland is not None else None,
                "awater": float(awater) if awater is not None else None,
                "aland_sqmi": float(aland_sqmi) if aland_sqmi is not None else None,
                "awater_sqmi": float(awater_sqmi) if awater_sqmi is not None else None,
                "intptlat": str(intptlat).strip() if intptlat else None,
                "intptlong": str(intptlong).strip() if intptlong else None,
                "ingestion_date": str(ingestion_date) if ingestion_date else None,
            })
    finally:
        cur.close()
    return result


# ---------------------------------------------------------------------------
# Drive sync — mount-first, rclone fallback (mirrors log_sync.py)
# ---------------------------------------------------------------------------

def _sync_via_mount(src: Path) -> bool:
    dest_dir = GDRIVE_MOUNT / WIKIDATA_GDRIVE_BASE
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        # Plain write avoids NTFS chmod errors on WSL2 Drive mounts (same trick as log_sync.py).
        dest.write_bytes(src.read_bytes())
        logger.success(f"Copied → {dest}")
        return True
    except Exception as exc:
        logger.warning(f"Drive mount copy failed: {exc}")
        return False


def _rclone_configured() -> bool:
    try:
        result = subprocess.run(
            ["rclone", "listremotes"], capture_output=True, text=True, timeout=10
        )
        return f"{RCLONE_REMOTE}:" in result.stdout
    except Exception:
        return False


def _sync_via_rclone(src: Path) -> bool:
    if not _rclone_configured():
        logger.warning(
            f"rclone remote '{RCLONE_REMOTE}' not configured. "
            "Run: rclone config  (add a remote named 'gdrive')"
        )
        return False
    remote_path = f"{RCLONE_REMOTE}:{WIKIDATA_GDRIVE_BASE}/{src.name}"
    try:
        result = subprocess.run(
            ["rclone", "copyto", str(src), remote_path, "--stats-one-line"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            logger.success(f"rclone → {remote_path}")
            return True
        logger.warning(f"rclone exited {result.returncode}: {result.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("rclone timed out after 300 s")
        return False
    except Exception as exc:
        logger.warning(f"rclone failed: {exc}")
        return False


def sync_to_drive(src: Path) -> bool:
    """Copy src to Google Drive. Tries mount first, falls back to rclone. Non-fatal."""
    logger.info(f"Syncing {src.name} to Drive  [{WIKIDATA_GDRIVE_BASE}]")
    if GDRIVE_MOUNT.exists():
        return _sync_via_mount(src)
    logger.debug(f"Drive mount {GDRIVE_MOUNT} not found — trying rclone")
    return _sync_via_rclone(src)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export bronze jurisdiction tables to JSON for Google Colab use"
    )
    parser.add_argument(
        "--states",
        default=",".join(PRIORITY_STATES),
        help=f"Comma-separated USPS codes (default: {','.join(PRIORITY_STATES)})",
    )
    parser.add_argument(
        "--all-us-states",
        action="store_true",
        default=False,
        help="Export all 52 USPS codes (50 states + DC + PR)",
    )
    parser.add_argument(
        "--output",
        default="data/cache/wikidata/bronze_jurisdictions.json",
        help="Local output path (default: data/cache/wikidata/bronze_jurisdictions.json)",
    )
    parser.add_argument(
        "--sync-to-drive",
        action="store_true",
        default=False,
        help=(
            "Copy the JSON to Google Drive after writing. "
            f"Uses mount at $LOG_GDRIVE_MOUNT ({GDRIVE_MOUNT}) or rclone remote '{RCLONE_REMOTE}'."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=(
            os.getenv("NEON_DATABASE_URL_DEV")
            or os.getenv("NEON_DATABASE_URL")
            or "postgresql://postgres:password@localhost:5433/open_navigator"
        ),
        help="Postgres connection string (default: env NEON_DATABASE_URL_DEV or NEON_DATABASE_URL)",
    )

    args = parser.parse_args()

    states: List[str]
    if args.all_us_states:
        states = sorted(STATE_NAMES.keys())
    else:
        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]

    unknown = [s for s in states if s not in STATE_NAMES]
    if unknown:
        raise SystemExit(f"Unknown USPS code(s): {', '.join(unknown)}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to Postgres…")
    conn = psycopg2.connect(args.database_url)
    t0 = time.perf_counter()
    try:
        logger.info(f"Exporting {len(states)} state(s): {', '.join(states)}")

        logger.info("  → municipalities…")
        municipalities = _export_municipalities(conn, states)

        logger.info("  → counties…")
        counties = _export_counties(conn, states)

        logger.info("  → school districts…")
        school_districts = _export_school_districts(conn, states)

        logger.info("  → states…")
        states_data = _export_states_table(conn, states)
    finally:
        conn.close()

    muni_total = sum(len(v) for v in municipalities.values())
    county_total = sum(len(v) for v in counties.values())
    school_total = sum(len(v) for v in school_districts.values())
    state_total = sum(len(v) for v in states_data.values())

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "states": states,
        "municipalities": municipalities,
        "counties": counties,
        "school_districts": school_districts,
        "states_data": states_data,
    }

    logger.info(f"Writing JSON to {out_path}…")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=None, separators=(",", ":"), default=str)

    elapsed = time.perf_counter() - t0
    size_mb = out_path.stat().st_size / 1_048_576
    logger.success(
        f"Exported in {elapsed:.1f}s → {out_path} ({size_mb:.2f} MB)\n"
        f"  states={state_total}  counties={county_total}  "
        f"municipalities={muni_total}  school_districts={school_total}"
    )

    if args.sync_to_drive:
        sync_to_drive(out_path)


if __name__ == "__main__":
    main()
