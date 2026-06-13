#!/usr/bin/env python3
"""Index locally-cached OpenStates bill PDFs into Databricks (Unity Catalog).

Companion to ``ingestion.openstates.bill_documents`` (the downloader). That job
lands PDFs + ``.pdf.json`` sidecars under ``data/cache/bills/`` on the local
disk — which a Databricks workspace cannot read directly. This job bridges the
gap, warehouse-only (no Spark cluster required):

  1. Upload each PDF to a Unity Catalog **Volume**, mirroring the local tree:
       /Volumes/<catalog>/<schema>/<volume>/<STATE>/<session>/<bill>/<file>.pdf
  2. Write a single consolidated **parquet manifest** of all sidecar metadata
     (one row per PDF: state/session/bill/kind/note/date/url/sha256/bytes/…/
     volume_path) and upload it under ``.../<volume>/_manifests/``.
  3. ``CREATE TABLE IF NOT EXISTS`` the index table and ``COPY INTO`` it from the
     manifests directory via the SQL warehouse. ``COPY INTO`` tracks already-
     loaded files, so re-runs are idempotent.

The index table (``<catalog>.<schema>.bill_pdf_index`` by default) is the thing
you query/index downstream; ``volume_path`` points at the binary for text
extraction. Uploads skip PDFs already present at the same byte size, so this is
safe to re-run as the downloader keeps filling the cache.

Credentials come from the environment (same as the rest of the repo):
    DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID
Optional target overrides:
    DATABRICKS_CATALOG (default: main), DATABRICKS_SCHEMA (default: open_navigator)

Usage:
    # preview what would upload, no network writes
    python -m ingestion.openstates.bill_documents_databricks --dry-run

    # full index into main.open_navigator.bill_pdf_index
    python -m ingestion.openstates.bill_documents_databricks

    # only refresh the manifest + table, don't re-upload PDFs
    python -m ingestion.openstates.bill_documents_databricks --manifest-only

    # scope to a state / cap for a smoke test
    python -m ingestion.openstates.bill_documents_databricks --state AL --limit 50
"""
from __future__ import annotations

import argparse
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

from loguru import logger

try:
    from core_lib.logging import setup_logging
except Exception:  # pragma: no cover - logging helper is best-effort
    def setup_logging() -> None:  # type: ignore[misc]
        pass

CACHE_DIR = Path("data/cache/bills")

DEFAULT_CATALOG = "main"
DEFAULT_SCHEMA = "open_navigator"
DEFAULT_VOLUME = "bill_pdfs"
DEFAULT_TABLE = "bill_pdf_index"

# Columns materialized into the manifest parquet (and the Delta index table),
# in declaration order. Keep in sync with _MANIFEST_DDL below.
MANIFEST_FIELDS: tuple[str, ...] = (
    "sha256",
    "kind",
    "state",
    "session",
    "bill_identifier",
    "note",
    "doc_date",
    "classification",
    "url",
    "media_type",
    "content_type",
    "http_status",
    "bytes",
    "fetched_at",
    "volume_path",
)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def resolve_databricks_config(
    catalog: str | None,
    schema: str | None,
    volume: str,
    table: str,
) -> dict[str, str]:
    """Resolve host/token/warehouse + target UC names (CLI overrides env)."""
    _load_env()
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
    missing = [
        name
        for name, val in (
            ("DATABRICKS_HOST", host),
            ("DATABRICKS_TOKEN", token),
            ("DATABRICKS_WAREHOUSE_ID", warehouse_id),
        )
        if not val
    ]
    if missing:
        raise SystemExit(
            "Missing Databricks credentials in env: " + ", ".join(missing)
        )
    return {
        "host": host,
        "token": token,
        "warehouse_id": warehouse_id,
        "catalog": catalog or os.getenv("DATABRICKS_CATALOG", DEFAULT_CATALOG),
        "schema": schema or os.getenv("DATABRICKS_SCHEMA", DEFAULT_SCHEMA),
        "volume": volume,
        "table": table,
    }


def iter_sidecars(
    cache_dir: Path, states: set[str] | None, limit: int | None
) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield (pdf_path, sidecar_meta) for every complete cached PDF.

    A PDF is complete when both the binary and a non-empty ``.pdf.json`` exist.
    Ordering is newest-first by the date prefix in the filename so a ``--limit``
    smoke test sees recent bills, mirroring the downloader's ordering intent.
    """
    n = 0
    sidecars = sorted(cache_dir.rglob("*.pdf.json"), reverse=True)
    for sc in sidecars:
        pdf = sc.with_suffix("")  # strip ".json" -> "....pdf"
        if not pdf.is_file() or pdf.stat().st_size == 0:
            continue
        try:
            meta = json.loads(sc.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("unreadable sidecar, skipping: {}", sc)
            continue
        state = (meta.get("state") or "").upper()
        if states is not None and state not in states:
            continue
        yield pdf, meta
        n += 1
        if limit is not None and n >= limit:
            return


def volume_path_for(pdf: Path, meta: dict[str, Any], cfg: dict[str, str]) -> str:
    """UC Volume path mirroring the local cache tree under the bills root."""
    rel = pdf.relative_to(CACHE_DIR)
    base = f"/Volumes/{cfg['catalog']}/{cfg['schema']}/{cfg['volume']}"
    return f"{base}/{rel.as_posix()}"


def manifest_row(meta: dict[str, Any], volume_path: str) -> dict[str, Any]:
    """Project a sidecar dict onto MANIFEST_FIELDS (typed for parquet)."""
    return {
        "sha256": meta.get("sha256"),
        "kind": meta.get("kind"),
        "state": (meta.get("state") or "").upper() or None,
        "session": meta.get("session"),
        "bill_identifier": meta.get("bill_identifier"),
        "note": meta.get("note"),
        "doc_date": meta.get("doc_date"),
        "classification": meta.get("classification"),
        "url": meta.get("url"),
        "media_type": meta.get("media_type"),
        "content_type": meta.get("content_type"),
        "http_status": (
            int(meta["http_status"]) if meta.get("http_status") is not None else None
        ),
        "bytes": int(meta["bytes"]) if meta.get("bytes") is not None else None,
        "fetched_at": meta.get("fetched_at"),
        "volume_path": volume_path,
    }


def _write_manifest_parquet(rows: list[dict[str, Any]], out_path: Path) -> Path:
    """Write the manifest rows to a local parquet (pyarrow), return the path."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    cols = {f: [r.get(f) for r in rows] for f in MANIFEST_FIELDS}
    schema = pa.schema(
        [
            pa.field("sha256", pa.string()),
            pa.field("kind", pa.string()),
            pa.field("state", pa.string()),
            pa.field("session", pa.string()),
            pa.field("bill_identifier", pa.string()),
            pa.field("note", pa.string()),
            pa.field("doc_date", pa.string()),
            pa.field("classification", pa.string()),
            pa.field("url", pa.string()),
            pa.field("media_type", pa.string()),
            pa.field("content_type", pa.string()),
            pa.field("http_status", pa.int32()),
            pa.field("bytes", pa.int64()),
            pa.field("fetched_at", pa.string()),
            pa.field("volume_path", pa.string()),
        ]
    )
    table = pa.table(cols, schema=schema)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path)
    return out_path


# DDL for the index table. PK is declared NOT ENFORCED (UC informational PK).
def _create_table_sql(cfg: dict[str, str]) -> str:
    fq = f"{cfg['catalog']}.{cfg['schema']}.{cfg['table']}"
    return f"""
        CREATE TABLE IF NOT EXISTS {fq} (
            sha256          STRING,
            kind            STRING,
            state           STRING,
            session         STRING,
            bill_identifier STRING,
            note            STRING,
            doc_date        STRING,
            classification  STRING,
            url             STRING,
            media_type      STRING,
            content_type    STRING,
            http_status     INT,
            bytes           BIGINT,
            fetched_at      STRING,
            volume_path     STRING,
            CONSTRAINT {cfg['table']}_pk PRIMARY KEY (sha256) NOT ENFORCED
        ) USING DELTA
    """


def _copy_into_sql(cfg: dict[str, str], manifest_dir: str) -> str:
    fq = f"{cfg['catalog']}.{cfg['schema']}.{cfg['table']}"
    cols = ", ".join(MANIFEST_FIELDS)
    return f"""
        COPY INTO {fq} ({cols})
        FROM (SELECT {cols} FROM '{manifest_dir}')
        FILEFORMAT = PARQUET
        FORMAT_OPTIONS ('mergeSchema' = 'true')
        COPY_OPTIONS ('mergeSchema' = 'true')
    """


def _run_sql(w: Any, cfg: dict[str, str], statement: str, label: str) -> None:
    """Execute a statement on the SQL warehouse and wait for it to finish."""
    logger.info("SQL: {}", label)
    resp = w.statement_execution.execute_statement(
        warehouse_id=cfg["warehouse_id"],
        catalog=cfg["catalog"],
        schema=cfg["schema"],
        statement=statement,
        wait_timeout="50s",
    )
    state = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
    statement_id = resp.statement_id
    # Poll if the warehouse is still working past the inline wait window.
    while state in ("PENDING", "RUNNING"):
        time.sleep(2)
        resp = w.statement_execution.get_statement(statement_id)
        state = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
    if state != "SUCCEEDED":
        err = getattr(resp.status, "error", None)
        raise RuntimeError(f"{label} failed ({state}): {err}")
    logger.success("SQL ok: {}", label)


def index_to_databricks(
    *,
    states: set[str] | None = None,
    limit: int | None = None,
    cache_dir: Path = CACHE_DIR,
    catalog: str | None = None,
    schema: str | None = None,
    volume: str = DEFAULT_VOLUME,
    table: str = DEFAULT_TABLE,
    manifest_only: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """Upload cached bill PDFs to a UC Volume + COPY their metadata into Delta.

    Returns counts: scanned / uploaded / skipped(exists) / failed / manifest_rows.
    """
    cfg = resolve_databricks_config(catalog, schema, volume, table)
    fq = f"{cfg['catalog']}.{cfg['schema']}.{cfg['table']}"
    logger.info(
        "Target: volume=/Volumes/{}/{}/{}  table={}  (manifest_only={} dry_run={})",
        cfg["catalog"], cfg["schema"], cfg["volume"], fq, manifest_only, dry_run,
    )

    counts = {
        "scanned": 0,
        "uploaded": 0,
        "skipped": 0,
        "failed": 0,
        "manifest_rows": 0,
    }
    rows: list[dict[str, Any]] = []

    w = None
    if not dry_run:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient(host=cfg["host"], token=cfg["token"])

    for pdf, meta in iter_sidecars(cache_dir, states, limit):
        counts["scanned"] += 1
        vpath = volume_path_for(pdf, meta, cfg)
        rows.append(manifest_row(meta, vpath))

        if manifest_only:
            continue
        if dry_run:
            if counts["scanned"] <= 20:
                logger.info("[dry-run] {} -> {}", pdf, vpath)
            continue

        size = pdf.stat().st_size
        try:
            existing = w.files.get_metadata(vpath)
            if getattr(existing, "content_length", None) == size:
                counts["skipped"] += 1
                continue
        except Exception:  # noqa: BLE001 - NotFound (and transient) => attempt upload
            pass

        try:
            with pdf.open("rb") as fh:
                w.files.upload(vpath, fh, overwrite=True)
            counts["uploaded"] += 1
        except Exception as exc:  # noqa: BLE001 - one bad file shouldn't abort
            counts["failed"] += 1
            logger.warning("upload failed {}: {}", vpath, exc)
        if counts["uploaded"] and counts["uploaded"] % 200 == 0:
            logger.info(
                "progress: uploaded={} skipped={} failed={} (scanned {})",
                counts["uploaded"], counts["skipped"], counts["failed"], counts["scanned"],
            )

    counts["manifest_rows"] = len(rows)
    logger.info("collected {} manifest row(s)", len(rows))

    if dry_run:
        logger.info("[dry-run] nothing uploaded; table {} untouched", fq)
        return counts
    if not rows:
        logger.warning("no cached PDFs matched; nothing to index")
        return counts

    # Write the manifest parquet locally, upload to the volume, COPY INTO Delta.
    local_manifest = cache_dir / "_manifests" / "bill_pdf_manifest.parquet"
    _write_manifest_parquet(rows, local_manifest)
    manifest_dir = f"/Volumes/{cfg['catalog']}/{cfg['schema']}/{cfg['volume']}/_manifests"
    # One manifest file per run, keyed by row count + newest fetched_at so COPY
    # INTO treats each run's manifest as a distinct (idempotent) load unit.
    newest = max((r.get("fetched_at") or "") for r in rows) or "manifest"
    stamp = newest.replace(":", "").replace("-", "").replace(".", "")[:15]
    remote_manifest = f"{manifest_dir}/bill_pdf_manifest_{len(rows)}_{stamp}.parquet"
    logger.info("uploading manifest -> {}", remote_manifest)
    with local_manifest.open("rb") as fh:
        w.files.upload(remote_manifest, fh, overwrite=True)

    _run_sql(w, cfg, _create_table_sql(cfg), f"create table {fq}")
    _run_sql(w, cfg, _copy_into_sql(cfg, manifest_dir), f"COPY INTO {fq}")

    logger.success(
        "done: scanned={scanned} uploaded={uploaded} skipped={skipped} "
        "failed={failed} manifest_rows={manifest_rows} -> {fq}",
        fq=fq, **counts,
    )
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Index cached OpenStates bill PDFs into a Databricks UC Volume + Delta table.",
    )
    parser.add_argument(
        "--state", nargs="*", dest="states",
        help="USPS code(s) to index, e.g. AL TX. Default: all cached states.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max PDFs to index (smoke test).")
    parser.add_argument("--catalog", default=None, help=f"UC catalog (default env/{DEFAULT_CATALOG}).")
    parser.add_argument("--schema", default=None, help=f"UC schema (default env/{DEFAULT_SCHEMA}).")
    parser.add_argument("--volume", default=DEFAULT_VOLUME, help=f"UC volume (default {DEFAULT_VOLUME}).")
    parser.add_argument("--table", default=DEFAULT_TABLE, help=f"Index table name (default {DEFAULT_TABLE}).")
    parser.add_argument(
        "--manifest-only", action="store_true",
        help="Skip PDF uploads; only (re)build the manifest + COPY INTO the table.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List planned uploads + target paths; no network writes.",
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    states = {s.upper() for s in args.states} if args.states else None
    index_to_databricks(
        states=states,
        limit=args.limit,
        catalog=args.catalog,
        schema=args.schema,
        volume=args.volume,
        table=args.table,
        manifest_only=args.manifest_only,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
