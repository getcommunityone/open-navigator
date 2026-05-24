#!/usr/bin/env python3
"""
wikidata_fips_gnis_extract_local.py
────────────────────────────────────
Extract FIPS (P774) and GNIS (P590) mappings from the Wikidata JSON dump
and save locally — no Databricks required.

Output: data/cache/wikidata/fips_gnis_map.parquet  (default)
        or a Postgres table via --postgres

Crash/resume safe: every 500k entities a checkpoint parquet + state file are
written. If the process dies, re-run with --resume and it will fast-forward
past already-scanned entities instead of starting from scratch.

If you see ``OSError: Invalid data stream`` from bz2, the local dump is almost
always truncated or corrupted — compare file size to Wikimedia’s dump and
``wget -c`` (or re-download). On that error the script flushes a final
checkpoint so rows found since the last periodic flush are not lost.

Usage:
    # Full dump → Parquet (default: local dump + resume if checkpoint exists)
    .venv/bin/python scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py

    # Ignore checkpoint and scan from the beginning
    .venv/bin/python scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py --no-resume

    # Save to Postgres instead of Parquet
    .venv/bin/python scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py --postgres

    # Quick test — stop after 500k entities (~2-3 min)
    .venv/bin/python scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py --limit 500000

    # Stream from Wikimedia over HTTP (no local .bz2)
    .venv/bin/python scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py --remote

    # Unreliable Wi‑Fi / WSL: resumable download, then extract from disk
    mkdir -p data/cache/wikidata/dumps
    wget -c -O data/cache/wikidata/dumps/latest-all.json.bz2 \\
      https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2
    .venv/bin/python scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py
"""

import argparse
import bz2
import json
import os
import sys
import time
from pathlib import Path

import requests
from loguru import logger

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

DUMP_URL     = "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"
DEFAULT_DUMP_FILE = Path(
    os.getenv("WIKIDATA_DUMP_FILE", ROOT / "data/cache/wikidata/dumps/latest-all.json.bz2")
)
OUTPUT_DIR   = Path(os.getenv("WIKIDATA_CACHE_DIR", ROOT / "data/cache/wikidata"))
PARQUET_PATH = OUTPUT_DIR / "fips_gnis_map.parquet"
CHECKPOINT_PATH = OUTPUT_DIR / "fips_gnis_map_checkpoint.parquet"
STATE_PATH   = OUTPUT_DIR / "fips_gnis_map_state.json"   # tracks entities_scanned for resume

# https://meta.wikimedia.org/wiki/User-Agent_policy
DUMP_HEADERS = {
    "User-Agent": os.getenv(
        "WIKIDATA_USER_AGENT",
        "OpenNavigator-fips-gnis-extract/1.0 (+https://github.com/getcommunityone/open-navigator)",
    ),
}

LOG_EVERY    = 100_000
FLUSH_EVERY  = 500_000   # checkpoint this often (entities)
CHUNK_SIZE   = 1024 * 1024 * 4  # 4 MB decompress buffer

PROP_FIPS = "P774"
PROP_GNIS = "P590"


# ── state helpers ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"entities_scanned": 0, "records_found": 0}


def save_state(entities_scanned: int, records_found: int) -> None:
    STATE_PATH.write_text(json.dumps({
        "entities_scanned": entities_scanned,
        "records_found": records_found,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2))


# ── extraction helpers ─────────────────────────────────────────────────────────

def extract_claim_values(entity: dict, prop: str) -> list[str]:
    claims = entity.get("claims", {}).get(prop, [])
    values = []
    for claim in claims:
        try:
            val = claim["mainsnak"]["datavalue"]["value"]
            if isinstance(val, str):
                values.append(val.strip())
        except (KeyError, TypeError):
            continue
    return values


def _yield_entities_from_bz2_lines(
    line_source,
    *,
    skip: int = 0,
    limit: int = 0,
    source_label: str = "dump",
):
    """Parse newline-delimited JSON entities from a bz2 byte line iterator."""
    if skip:
        logger.info(f"Fast-forwarding past {skip:,} already-scanned entities…")

    scanned = 0
    yielded = 0

    for raw_line in line_source:
        line = raw_line.strip() if isinstance(raw_line, bytes) else raw_line.strip().encode("utf-8")
        if not line or line in (b"[", b"]"):
            continue
        line = line.rstrip(b",")
        try:
            entity = json.loads(line)
        except json.JSONDecodeError:
            continue

        scanned += 1

        if scanned <= skip:
            if skip and scanned % LOG_EVERY == 0:
                logger.info(f"Fast-forward: {scanned:,}/{skip:,} ({100 * scanned / skip:.0f}%)")
            continue

        yield entity
        yielded += 1

        if limit and yielded >= limit:
            logger.info(f"--limit {limit} reached, stopping.")
            return

    logger.debug(f"Finished reading {source_label}: scanned={scanned:,} yielded={yielded:,}")


def _iter_bz2_lines_from_http(url: str):
    """Yield raw lines from a remote .json.bz2 dump (may drop on long flaky links)."""
    with requests.get(url, stream=True, timeout=(30, 600), headers=DUMP_HEADERS) as resp:
        resp.raise_for_status()
        decompressor = bz2.BZ2Decompressor()
        buffer = b""
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            buffer += decompressor.decompress(chunk)
            lines = buffer.split(b"\n")
            buffer = lines[-1]
            for line in lines[:-1]:
                yield line


def _iter_bz2_lines_from_file(path: Path):
    """Yield raw lines from a local .json.bz2 dump (use wget -c for resumable download)."""
    with bz2.open(path, "rb") as fh:
        for line in fh:
            yield line


def stream_wikidata_dump(
    url: str,
    skip: int = 0,
    limit: int = 0,
    dump_file: Path | None = None,
):
    """
    Stream the bz2 Wikidata dump line by line. Yields parsed entity dicts.

    skip      — fast-forward past this many entities before yielding (for resume)
    limit     — stop after yielding this many entities (0 = no limit)
    dump_file — if set, read from local .bz2 (recommended when HTTP streams drop)
    """
    if dump_file is not None:
        dump_file = dump_file.resolve()
        if not dump_file.is_file():
            raise FileNotFoundError(
                f"Dump file not found: {dump_file}\n"
                "Download with:\n"
                f"  mkdir -p {dump_file.parent}\n"
                f"  wget -c -O {dump_file} {url}"
            )
        logger.info(f"Reading dump from local file: {dump_file} ({dump_file.stat().st_size / 1e9:.1f} GB)")
        line_iter = _iter_bz2_lines_from_file(dump_file)
        source_label = str(dump_file)
    else:
        logger.info(f"Streaming dump from {url}")
        logger.info(
            "Tip: if you see ChunkedEncodingError/IncompleteRead, download the .bz2 with "
            "wget -c and re-run with --dump-file (see script docstring)."
        )
        line_iter = _iter_bz2_lines_from_http(url)
        source_label = url

    yield from _yield_entities_from_bz2_lines(
        line_iter, skip=skip, limit=limit, source_label=source_label
    )


def entity_to_records(entity: dict) -> list[dict]:
    if entity.get("type") != "item":
        return []

    qid       = entity.get("id", "")
    fips_vals = extract_claim_values(entity, PROP_FIPS)
    gnis_vals = extract_claim_values(entity, PROP_GNIS)

    if not fips_vals and not gnis_vals:
        return []

    label    = entity.get("labels", {}).get("en", {}).get("value", "")
    modified = entity.get("lastrevid")

    rows = []
    for fips in fips_vals:
        rows.append({
            "qid":      qid,
            "label":    label,
            "fips":     fips,
            "gnis":     gnis_vals[0] if gnis_vals else None,
            "modified": modified,
            "source":   "fips",
        })
    if not fips_vals:
        for gnis in gnis_vals:
            rows.append({
                "qid":      qid,
                "label":    label,
                "fips":     None,
                "gnis":     gnis,
                "modified": modified,
                "source":   "gnis",
            })
    return rows


# ── checkpointing ──────────────────────────────────────────────────────────────

def flush_checkpoint(records: list[dict], entities_scanned: int) -> None:
    """Overwrite checkpoint parquet and state file with current progress."""
    import pandas as pd

    df = pd.DataFrame(records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CHECKPOINT_PATH, index=False)
    save_state(entities_scanned, len(records))
    logger.info(
        f"Checkpoint: {entities_scanned:,} entities scanned, "
        f"{len(records):,} matches → {CHECKPOINT_PATH}"
    )


def load_checkpoint() -> list[dict]:
    """Load records saved by a previous interrupted run."""
    if CHECKPOINT_PATH.exists():
        import pandas as pd
        df = pd.read_parquet(CHECKPOINT_PATH)
        logger.info(f"Loaded {len(df):,} records from checkpoint {CHECKPOINT_PATH}")
        return df.to_dict("records")
    return []


# ── sinks ──────────────────────────────────────────────────────────────────────

def save_to_parquet(records: list[dict], path: Path) -> None:
    import pandas as pd
    df = pd.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info(f"Saved {len(df):,} rows → {path}")


def save_to_postgres(records: list[dict]) -> None:
    import psycopg2
    from psycopg2.extras import execute_values

    db_url = (
        os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("DATABASE_URL")
        or "postgresql://postgres:postgres@localhost:5432/open_navigator_stats"
    )
    logger.info(f"Writing {len(records):,} rows to Postgres (bronze.bronze_jurisdiction_wikidata_fips_gnis_map)…")

    conn = psycopg2.connect(db_url)
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_wikidata_fips_gnis_map (
                    qid      TEXT NOT NULL,
                    label    TEXT,
                    fips     TEXT,
                    gnis     TEXT,
                    modified BIGINT,
                    source   TEXT,
                    PRIMARY KEY (qid, fips, gnis)
                )
            """)
            execute_values(
                cur,
                """
                INSERT INTO bronze.bronze_jurisdiction_wikidata_fips_gnis_map (qid, label, fips, gnis, modified, source)
                VALUES %s
                ON CONFLICT (qid, fips, gnis) DO UPDATE
                  SET label = EXCLUDED.label, modified = EXCLUDED.modified
                """,
                [
                    (r["qid"], r["label"], r["fips"], r["gnis"], r["modified"], r["source"])
                    for r in records
                ],
            )
    conn.close()
    logger.info("Postgres write complete.")


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Extract FIPS/GNIS from Wikidata dump — local, no Databricks"
    )
    ap.add_argument("--postgres", action="store_true", help="Write to Postgres instead of Parquet")
    ap.add_argument("--output",   default=str(PARQUET_PATH), help=f"Parquet output path (default: {PARQUET_PATH})")
    ap.add_argument("--limit",    type=int, default=0, help="Stop after N entities (for testing)")
    ap.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume a previous interrupted run (default: on). Skips already-scanned entities and keeps "
        "checkpoint matches. Use --no-resume to start from scratch.",
    )
    ap.add_argument("--remote", action="store_true",
                    help="Stream the dump from --url instead of reading the local --dump-file.")
    ap.add_argument("--url",      default=DUMP_URL, help="Override dump URL")
    ap.add_argument(
        "--dump-file",
        default=str(DEFAULT_DUMP_FILE),
        help=f"Local .json.bz2 path (default: env WIKIDATA_DUMP_FILE or {DEFAULT_DUMP_FILE}). "
        "Use after wget -c; avoids ChunkedEncodingError on long HTTP streams.",
    )
    args = ap.parse_args()

    output_path = Path(args.output)

    # ── resume: load prior state ───────────────────────────────────────────────
    skip_entities = 0
    records: list[dict] = []

    if args.resume:
        state = load_state()
        skip_entities = state.get("entities_scanned", 0)
        if skip_entities:
            logger.info(
                f"Resuming from entity {skip_entities:,} "
                f"(checkpoint had {state.get('records_found', 0):,} matches)"
            )
            records = load_checkpoint()
        else:
            logger.info("No checkpoint found — starting from scratch.")
    else:
        # Warn if stale checkpoint exists but --resume wasn't passed
        if STATE_PATH.exists():
            state = load_state()
            if state.get("entities_scanned", 0):
                logger.warning(
                    f"Found a checkpoint at {state['entities_scanned']:,} entities "
                    f"but --no-resume was passed — starting from scratch and overwriting it. "
                    "Re-run without --no-resume to continue from where it left off."
                )

    entity_count = skip_entities   # total entities seen (including skipped)
    start = time.time()

    logger.info("Starting Wikidata FIPS/GNIS extraction (local — no Databricks needed)")
    logger.info(f"Output: {'Postgres' if args.postgres else output_path}")

    dump_file = None if args.remote else Path(args.dump_file)
    try:
        for entity in stream_wikidata_dump(
            args.url, skip=skip_entities, limit=args.limit, dump_file=dump_file
        ):
            entity_count += 1
            records.extend(entity_to_records(entity))

            if entity_count % LOG_EVERY == 0:
                elapsed = time.time() - start
                logger.info(
                    f"Entities: {entity_count:,} | Matches: {len(records):,} | "
                    f"Elapsed: {elapsed/60:.1f}m"
                )

            if not args.postgres and entity_count % FLUSH_EVERY == 0:
                flush_checkpoint(records, entity_count)
    except (OSError, EOFError) as e:
        elapsed = time.time() - start
        logger.exception(
            "Dump read failed after {:.1f}m at entity_count={:,} (last entity fully parsed).",
            elapsed / 60,
            entity_count,
        )
        if dump_file is not None and dump_file.is_file():
            sz = dump_file.stat().st_size
            logger.error(
                "Local bz2 read error ({!r}). This usually means the file is truncated or corrupt — "
                "not a bug in the extractor. Fix: compare size to the dump server, then "
                "`wget -c -O {} {}` (or delete and re-download).",
                e,
                dump_file,
                args.url,
            )
            logger.error("Local dump size: {:,} bytes ({:.1f} GB)", sz, sz / 1e9)
        if not args.postgres and records and entity_count > skip_entities:
            flush_checkpoint(records, entity_count)
            logger.warning(
                "Wrote emergency checkpoint so matches up to this point are preserved; "
                "--resume will still re-scan from the start of the file to fast-forward "
                "to entity {:,} (slow on huge dumps until the file is repaired).",
                entity_count,
            )
        raise SystemExit(1) from e

    elapsed = time.time() - start
    logger.info(
        f"Scan complete: {entity_count:,} entities, "
        f"{len(records):,} FIPS/GNIS records in {elapsed/3600:.1f}h"
    )

    if args.postgres:
        save_to_postgres(records)
    else:
        save_to_parquet(records, output_path)
        # Clean up checkpoint files now that we have the final output
        for p in (CHECKPOINT_PATH, STATE_PATH):
            if p.exists():
                p.unlink()

    logger.info(f"Done. Join against '{output_path}' locally — no more SPARQL timeouts.")


if __name__ == "__main__":
    main()
