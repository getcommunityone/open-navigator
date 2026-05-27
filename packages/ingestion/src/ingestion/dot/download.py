#!/usr/bin/env python3
"""Download-only: State DOT public involvement / hearings portal pages.

Reads the markdown table in ``dot.txt`` (State | markdown link | hearings note),
maps state names to USPS codes, and fetches each primary portal URL into the
local cache:

  data/cache/dot/{USPS}/public_involvement.html  (or .pdf when the portal is a PDF)
  data/cache/dot/{USPS}/source.json              (per-state fetch metadata)

The state pages span many different hosts, so requests use a hostless
``base_url`` and absolute URLs are passed straight to the client. A modest
rate limit is applied because the run loops over ~50 states.

This module is download-only. Loading the snapshots into the database is the
job of ``ingestion.dot.events``.

Usage:
    python -m ingestion.dot.download --all
    python -m ingestion.dot.download --states AL TX GA
    python -m ingestion.dot.download --states AL --force
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging
from loguru import logger


# dot.txt is shipped alongside this module (the registry of state -> portal URL).
DEFAULT_DOT_MD = Path(__file__).resolve().parent / "dot.txt"
CACHE_DIR = Path("data/cache/dot")

# Consider a cached file fresh for this long before re-fetching.
CACHE_MAX_AGE_S = 7 * 24 * 60 * 60  # 7 days

USER_AGENT = (
    "OpenNavigatorDotResearch/1.0 (+https://github.com/getcommunityone/open-navigator-for-engagement; "
    "state DOT public involvement snapshots)"
)

# Full state / DC name -> USPS (must match rows in dot.txt first column)
STATE_NAME_TO_USPS: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}


def strip_tracking_params(url: str) -> str:
    p = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    new_query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def parse_dot_markdown_table(path: Path) -> list[dict[str, Any]]:
    """Parse ``dot.txt`` pipe table: state name, markdown link cell, hearings column."""
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    link_re = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
    for line in text.splitlines():
        line = line.rstrip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        state_name = parts[1]
        if state_name == "State" or not state_name:
            continue
        if set(state_name) <= {"-", " "} or state_name.replace("-", "").strip() == "":
            continue
        link_cell = parts[2]
        hearings_note = parts[3] if len(parts) > 3 else ""
        m = link_re.search(link_cell)
        if not m:
            continue
        portal_label, url = m.group(1).strip(), strip_tracking_params(m.group(2).strip())
        usps = STATE_NAME_TO_USPS.get(state_name)
        if not usps:
            logger.warning("No USPS mapping for state name {!r}; skip", state_name)
            continue
        rows.append(
            {
                "state_usps": usps,
                "state_name": state_name,
                "portal_label": portal_label,
                "public_involvement_url": url,
                "hearings_note": hearings_note,
            }
        )
    return rows


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_registry(dot_md: Path = DEFAULT_DOT_MD) -> dict[str, dict[str, Any]]:
    """Parse the markdown table and index rows by USPS code."""
    rows = parse_dot_markdown_table(dot_md)
    if not rows:
        raise ValueError(f"No rows parsed from {dot_md}")
    return {r["state_usps"]: r for r in rows}


def _primary_path(usps: str, url: str) -> Path:
    """Cache path for a state's primary snapshot (.pdf for PDF portals, else .html)."""
    is_pdf = url.lower().split("?")[0].endswith(".pdf")
    suffix = "pdf" if is_pdf else "html"
    return CACHE_DIR / usps / f"public_involvement.{suffix}"


def _is_fresh(path: Path, max_age_s: float = CACHE_MAX_AGE_S) -> bool:
    """True if ``path`` exists, is non-empty, and was modified within ``max_age_s``."""
    if not path.is_file():
        return False
    if path.stat().st_size == 0:
        return False
    return (time.time() - path.stat().st_mtime) <= max_age_s


def _select_states(
    registry: dict[str, dict[str, Any]],
    states: list[str] | None,
) -> list[str]:
    """Resolve the list of USPS codes to fetch (all when ``states`` is None)."""
    available = sorted(registry)
    if not states:
        return available
    selected = [s.strip().upper() for s in states if s.strip()]
    bad = [s for s in selected if s not in registry]
    if bad:
        raise ValueError(f"Unknown USPS codes (not in table): {bad}")
    return selected


async def download(
    *,
    force: bool = False,
    states: list[str] | None = None,
    dot_md: Path = DEFAULT_DOT_MD,
    **params: Any,
) -> list[Path]:
    """Fetch each state's DOT public-involvement portal page into ``CACHE_DIR``.

    Each portal lives on its own host, so absolute URLs are passed to the
    rate-limited client. Returns the list of primary snapshot paths written
    (or reused from a fresh cache when ``force`` is False).
    """
    registry = load_registry(dot_md)
    selected = _select_states(registry, states)

    config = HttpClientConfig(
        base_url="",
        source="dot",
        timeout_s=45.0,
        rate_limit_per_sec=5.0,
        default_headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        },
    )

    written: list[Path] = []
    async with BaseAsyncClient(config) as client:
        for usps in selected:
            rec = registry[usps]
            url = rec["public_involvement_url"]
            primary = _primary_path(usps, url)

            if not force and _is_fresh(primary):
                logger.info("{} cache hit, skip fetch -> {}", usps, primary)
                written.append(primary)
                continue

            try:
                resp = await client.get(url)
            except Exception as exc:  # noqa: BLE001 - one bad state shouldn't abort the run
                logger.error("{} fetch failed {}: {}", usps, url, exc)
                continue

            body = resp.content
            if not body:
                logger.warning("{} empty body from {}", usps, url)
                continue

            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower() or None
            primary.parent.mkdir(parents=True, exist_ok=True)
            primary.write_bytes(body)

            meta = {
                "state_usps": usps,
                "state_name": rec["state_name"],
                "portal_label": rec["portal_label"],
                "source_url": url,
                "hearings_note": rec["hearings_note"],
                "http_status": resp.status_code,
                "content_type": ctype,
                "bytes": len(body),
                "sha256": sha256_bytes(body),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            (primary.parent / "source.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )
            logger.info("{} saved {} bytes -> {}", usps, len(body), primary)
            written.append(primary)

    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download state DOT public involvement portal pages (download-only).",
    )
    parser.add_argument(
        "--states",
        nargs="*",
        help="USPS codes to fetch (e.g. AL TX GA). Default: all states in the table.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when a fresh cached snapshot exists.",
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    paths = asyncio.run(download(force=args.force, states=args.states))
    logger.info("Wrote/reused {} state snapshot(s)", len(paths))


if __name__ == "__main__":
    main()
