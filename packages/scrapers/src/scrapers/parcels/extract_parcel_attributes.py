#!/usr/bin/env python3
"""
Attribute-only harvest from a county or state Esri parcel FeatureServer/MapServer.

Queries with returnGeometry=false so only tabular fields (owner, value, situs
address, legal description, etc.) are transferred. There is no nationwide free
parcel layer; each jurisdiction publishes its own REST endpoint (see README).

Usage:
    python scripts/datasources/parcels/extract_parcel_attributes.py \\
        --url "https://gis.example.gov/arcgis/rest/services/Parcels/FeatureServer/0/query" \\
        --output data/cache/parcels/example_county.csv

    python scripts/datasources/parcels/extract_parcel_attributes.py \\
        --url "https://gis.example.gov/.../FeatureServer/0" \\
        --normalize-fields \\
        --list-fields
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from loguru import logger

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from esri_endpoints import layer_metadata_url, normalize_query_url  # noqa: E402
from field_mappings import normalize_column_names  # noqa: E402

DEFAULT_CACHE_DIR = Path("data/cache/parcels")
DEFAULT_CHUNK_SIZE = 2000
DEFAULT_THROTTLE_SEC = 0.5
DEFAULT_TIMEOUT_SEC = 60
MAX_RETRIES = 5


def fetch_layer_field_names(query_url: str, timeout: int = DEFAULT_TIMEOUT_SEC) -> list[str]:
    meta_url = layer_metadata_url(query_url)
    resp = requests.get(meta_url, params={"f": "json"}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"ArcGIS metadata error: {data['error']}")
    fields = data.get("fields") or []
    return [str(f["name"]) for f in fields if f.get("name")]


def _request_page(
    query_url: str,
    params: dict[str, Any],
    *,
    offset: int,
    timeout: int,
) -> dict[str, Any]:
    page_params = {**params, "resultOffset": offset}
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(query_url, params=page_params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", data["error"]))
            return data
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            wait = min(5 * attempt, 30)
            logger.warning(
                "Request failed at offset {} (attempt {}/{}): {} — retry in {}s",
                offset,
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries at offset {offset}") from last_error


def extract_parcel_attributes(
    target_url: str,
    *,
    output_csv: Path | None = None,
    where: str = "1=1",
    out_fields: str = "*",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    throttle_sec: float = DEFAULT_THROTTLE_SEC,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_records: int | None = None,
    normalize_fields: bool = False,
) -> pd.DataFrame:
    """
    Paginate an Esri layer query and return attributes only (no geometry).

    If output_csv is set, writes a flat CSV under that path.
    """
    query_url = normalize_query_url(target_url)
    logger.info("Query endpoint: {}", query_url)
    logger.info("Harvesting attributes (returnGeometry=false)...")

    params: dict[str, Any] = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": chunk_size,
    }

    chunks: list[pd.DataFrame] = []
    offset = 0
    total = 0

    while True:
        if max_records is not None and total >= max_records:
            break

        page_cap = chunk_size
        if max_records is not None:
            page_cap = min(chunk_size, max_records - total)

        params["resultRecordCount"] = page_cap
        data = _request_page(query_url, params, offset=offset, timeout=timeout_sec)

        features = data.get("features") or []
        if not features:
            break

        rows = [f["attributes"] for f in features if "attributes" in f]
        if not rows:
            break

        chunks.append(pd.DataFrame(rows))
        total += len(rows)
        logger.info("Harvested {} rows (cumulative {:,})", len(rows), total)

        if max_records is not None and total >= max_records:
            break

        if not data.get("exceededTransferLimit", False) and len(features) < page_cap:
            break

        offset += len(rows)
        if throttle_sec > 0:
            time.sleep(throttle_sec)

    if not chunks:
        logger.warning("No records harvested.")
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    if normalize_fields:
        df = normalize_column_names(df)
        logger.info("Applied canonical field renames where aliases matched.")

    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False)
        logger.success("Wrote {:,} rows to {}", len(df), output_csv.resolve())

    return df


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract tabular parcel attributes from an Esri FeatureServer/MapServer layer.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Layer query URL or layer root (.../FeatureServer/0); /query is appended if missing.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output CSV path (default: data/cache/parcels/<host>_<layer>.csv)",
    )
    parser.add_argument("--where", default="1=1", help="Esri SQL where clause (default: 1=1)")
    parser.add_argument(
        "--out-fields",
        default="*",
        help="Comma-separated field list or * for all attributes",
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--throttle", type=float, default=DEFAULT_THROTTLE_SEC)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Stop after N rows (useful for smoke tests)",
    )
    parser.add_argument(
        "--normalize-fields",
        action="store_true",
        help="Rename known county-specific columns to canonical names (see field_mappings.py)",
    )
    parser.add_argument(
        "--list-fields",
        action="store_true",
        help="Print layer field names from metadata and exit",
    )
    args = parser.parse_args()

    query_url = normalize_query_url(args.url)

    if args.list_fields:
        names = fetch_layer_field_names(query_url, timeout=args.timeout)
        for name in names:
            print(name)
        return 0

    output = args.output
    if output is None:
        DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        host = urlparse(query_url).netloc.replace(".", "_")
        layer_bits = Path(urlparse(query_url).path).parts
        layer_id = layer_bits[-2] if layer_bits and layer_bits[-1].lower() == "query" else "layer"
        output = DEFAULT_CACHE_DIR / f"{host}_{layer_id}.csv"

    extract_parcel_attributes(
        args.url,
        output_csv=output,
        where=args.where,
        out_fields=args.out_fields,
        chunk_size=args.chunk_size,
        throttle_sec=args.throttle,
        timeout_sec=args.timeout,
        max_records=args.max_records,
        normalize_fields=args.normalize_fields,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
