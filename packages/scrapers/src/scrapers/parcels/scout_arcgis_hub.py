#!/usr/bin/env python3
"""
Discover public parcel/property layers via the ArcGIS Hub catalog API.

Paginates https://hub.arcgis.com/api/v3/datasets and keeps FeatureServer/MapServer
layer URLs suitable for attribute-only extraction.

Usage:
    python packages/scrapers/src/scrapers/parcels/scout_arcgis_hub.py --pages 5 \\
        --output data/cache/parcels/hub_discovered_endpoints.csv

    python packages/scrapers/src/scrapers/parcels/scout_arcgis_hub.py --pages 2 --validate --validate-limit 20
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from loguru import logger

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from esri_endpoints import is_esri_layer_url  # noqa: E402
from parse_openaddresses_sources import validate_seed_frame  # noqa: E402

HUB_DATASETS_URL = "https://hub.arcgis.com/api/v3/datasets"
DEFAULT_OUTPUT = Path("data/cache/parcels/hub_discovered_endpoints.csv")
DEFAULT_PAGE_SIZE = 100
DEFAULT_THROTTLE_SEC = 1.0


def scout_arcgis_hub(
    *,
    query: str = "parcels",
    tags_filter: str = "any(property,cadastral,parcel)",
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = 10,
    throttle_sec: float = DEFAULT_THROTTLE_SEC,
    timeout: int = 30,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    client = session or requests.Session()
    params: dict[str, Any] = {
        "q": query,
        "page[size]": page_size,
    }
    if tags_filter:
        params["filter[tags]"] = tags_filter

    records: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params["page[number]"] = page
        logger.info("Scouting ArcGIS Hub page {}...", page)
        try:
            resp = client.get(HUB_DATASETS_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            logger.error("Hub API error on page {}: {}", page, exc)
            break

        items = payload.get("data") or []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or {}
            if not isinstance(attrs, dict):
                continue
            server_url = attrs.get("url")
            if not server_url or not is_esri_layer_url(str(server_url)):
                continue
            records.append(
                {
                    "title": attrs.get("name"),
                    "organization": attrs.get("owner") or attrs.get("source"),
                    "source_endpoint": str(server_url).strip(),
                    "hub_id": item.get("id") or attrs.get("id"),
                    "item_id": attrs.get("itemId"),
                    "hub_type": attrs.get("hubType") or attrs.get("type"),
                    "geometry_type": attrs.get("geometryType"),
                    "record_count": attrs.get("recordCount"),
                    "server_capabilities": attrs.get("serverCapabilities"),
                    "categories": ",".join(attrs.get("categories") or [])
                    if isinstance(attrs.get("categories"), list)
                    else attrs.get("categories"),
                }
            )

        meta = payload.get("meta") or {}
        total_pages = meta.get("totalPages") or meta.get("total_pages")
        if total_pages and page >= int(total_pages):
            break
        if len(items) < page_size:
            break
        if throttle_sec > 0:
            time.sleep(throttle_sec)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["source_endpoint"], keep="first")
    return df.reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover parcel Esri layers from ArcGIS Hub.")
    parser.add_argument("--query", "-q", default="parcels", help="Hub search query")
    parser.add_argument(
        "--tags-filter",
        default="any(property,cadastral,parcel)",
        help="Hub filter[tags] value (empty string to omit)",
    )
    parser.add_argument("--pages", type=int, default=5, help="Maximum pages to fetch")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--throttle", type=float, default=DEFAULT_THROTTLE_SEC)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--validate", action="store_true", help="Probe ?f=json on each URL")
    parser.add_argument("--validate-limit", type=int, default=None)
    parser.add_argument("--validate-throttle", type=float, default=0.25)
    args = parser.parse_args()

    df = scout_arcgis_hub(
        query=args.query,
        tags_filter=args.tags_filter,
        page_size=args.page_size,
        max_pages=args.pages,
        throttle_sec=args.throttle,
        timeout=args.timeout,
    )
    if df.empty:
        logger.warning("No Esri endpoints discovered.")
        return 1

    logger.info("Discovered {:,} unique Esri layer URLs", len(df))

    if args.validate:
        to_check = df.head(args.validate_limit) if args.validate_limit else df
        validated = validate_seed_frame(
            to_check,
            url_column="source_endpoint",
            throttle_sec=args.validate_throttle,
            timeout=args.timeout,
        )
        if args.validate_limit and len(df) > len(to_check):
            rest = df.iloc[len(to_check) :].copy()
            for col in validated.columns:
                if col not in rest.columns and col not in df.columns:
                    continue
                if col not in ("source_endpoint", "title", "organization", "hub_id"):
                    rest[col] = None
            df = pd.concat([validated, rest], ignore_index=True)
        else:
            df = validated
        live = int(df["ok"].fillna(False).sum()) if "ok" in df.columns else 0
        logger.info("Queryable layers: {:,} / {:,}", live, len(to_check))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    logger.success("Wrote {:,} rows to {}", len(df), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
