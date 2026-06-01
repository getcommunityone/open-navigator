#!/usr/bin/env python3
"""CivicSearch topic-table FETCH: extract the policy-topic decoder baked into
the frontend bundle into ``data/cache/civicsearch/<portal>/topics.json``.

Why this exists
---------------
The CivicSearch JSON API never returns topic *names*. Search results, snippets
and ``get_topics_by_city`` all carry a bare numeric ``topic_id`` only (``-1`` ==
untopiced), and ``search.topic_counts`` is just ``[id, count]`` pairs. The
``id -> {name, query_id, keyword_stats}`` lookup lives ONLY in the site's
``main.js`` bundle as a static array (consumed there via ``fromId(topic_id)``).
This FETCH downloads that bundle and extracts the array verbatim so a
``topic_id`` landed in ``bronze_events_civicsearch(_schools)`` can be decoded
downstream (joined to a topic name in dbt).

Topic ids are PORTAL-SPECIFIC: the ``cities`` and ``schools`` properties number
their topics independently, so each portal gets its own ``topics.json`` (and its
own bronze landing table). Decode a ``topic_id`` only against the matching
portal's table.

Output (FETCH-only — landing is ``ingestion.civicsearch.topics``):
  * ``data/cache/civicsearch/<portal>/topics.json`` — JSON array of objects
    ``{id, name, query_id, keyword_stats}`` sorted by id.

Usage (repo root):
    python -m scrapers.civicsearch.topics --portal cities
    python -m scrapers.civicsearch.topics --portal schools
    python -m scrapers.civicsearch.topics --portal both
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

import httpx
from core_lib.logging import setup_logging
from loguru import logger

from .client import PORTAL_BASE_URLS, PORTALS, USER_AGENT

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CACHE = REPO_ROOT / "data" / "cache" / "civicsearch"

# The four bare object keys the bundle uses for each topic entry. The decoder
# array is a JS object-literal list like
#   [{id:-1,keyword_stats:["…"],name:"Local governance",query_id:"…"}, …]
# which is valid JSON once these bare keys are double-quoted.
_TOPIC_KEYS = ("id", "keyword_stats", "name", "query_id")
_QUOTE_KEYS_RE = re.compile(r"([{,])(" + "|".join(_TOPIC_KEYS) + r"):")


def _bundle_url(portal: str) -> str:
    """The site's main.js bundle URL for a portal (the bundle holds the topic
    table; the JSON API does not). Derived from the portal's ``/api/`` base."""
    base = PORTAL_BASE_URLS[portal]  # e.g. "https://www.civicsearch.org/api/"
    return base.rsplit("api/", 1)[0] + "main.js"


def _extract_topics_array(js: str) -> str:
    """Slice the topic-decoder array literal out of a main.js bundle.

    The array is the only ``[{…}]`` whose objects carry ``keyword_stats``. We
    anchor on the first ``keyword_stats`` occurrence, take the ``[{`` that opens
    its enclosing array, then string-aware bracket-match forward to the matching
    ``]``. Returns the raw JS source of the array (still object-literal syntax).
    """
    anchor = js.find("keyword_stats")
    if anchor == -1:
        raise ValueError("no 'keyword_stats' marker found in bundle (layout changed?)")
    start = js.rfind("[{", 0, anchor)
    if start == -1:
        raise ValueError("could not locate the opening '[{' of the topics array")

    depth = 0
    in_str = False
    esc = False
    quote = ""
    i = start
    n = len(js)
    while i < n:
        c = js[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                in_str = False
        elif c in "\"'":
            in_str = True
            quote = c
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
        i += 1
    raise ValueError("unterminated topics array in bundle")


def extract_topics(js: str) -> list[dict[str, Any]]:
    """Parse the topic decoder out of a main.js bundle into normalized dicts.

    Each entry is ``{id:int, name:str, query_id:str|None, keyword_stats:[str]}``,
    sorted by id. ``id == -1`` (the catch-all bucket) is kept. Raises on a layout
    the extractor no longer recognizes rather than landing partial garbage.
    """
    arr_src = _extract_topics_array(js)
    as_json = _QUOTE_KEYS_RE.sub(r'\1"\2":', arr_src)
    raw = json.loads(as_json)
    if not isinstance(raw, list) or not raw:
        raise ValueError("extracted topics array is empty or not a list")

    topics: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict) or "id" not in entry or "name" not in entry:
            raise ValueError(f"unexpected topic entry shape: {entry!r}")
        kw = entry.get("keyword_stats") or []
        topics.append(
            {
                "id": int(entry["id"]),
                "name": str(entry["name"]),
                "query_id": entry.get("query_id"),
                "keyword_stats": [str(k) for k in kw],
            }
        )
    topics.sort(key=lambda t: t["id"])
    return topics


async def fetch_topics(portal: str, *, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Download the portal's main.js bundle and extract its topic decoder."""
    if portal not in PORTAL_BASE_URLS:
        raise ValueError(f"portal must be one of {PORTALS}, got {portal!r}")
    url = _bundle_url(portal)
    logger.info("Fetching {} topic bundle: {}", portal, url)
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        topics = extract_topics(resp.text)
    logger.success("Extracted {} {} topics (id {}..{})", len(topics), portal,
                   topics[0]["id"], topics[-1]["id"])
    return topics


def topics_path(portal: str, *, cache_root: Path = DEFAULT_CACHE) -> Path:
    return cache_root / portal / "topics.json"


def write_topics(
    portal: str, topics: list[dict[str, Any]], *, cache_root: Path = DEFAULT_CACHE
) -> Path:
    """Write the portal's topic table to ``<portal>/topics.json`` (pretty JSON)."""
    out = topics_path(portal, cache_root=cache_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(topics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.success("Wrote {} topics -> {}", len(topics), out)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract the CivicSearch topic decoder from a portal's main.js "
        "bundle into data/cache/civicsearch/<portal>/topics.json"
    )
    parser.add_argument(
        "--portal",
        choices=(*PORTALS, "both"),
        default="both",
        help="Which property to fetch ('cities', 'schools', or 'both').",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE,
        help="Override the data/cache/civicsearch root (mostly for tests).",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    portals = PORTALS if args.portal == "both" else (args.portal,)
    for portal in portals:
        topics = await fetch_topics(portal)
        write_topics(portal, topics, cache_root=args.cache_root)


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
