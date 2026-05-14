#!/usr/bin/env python3
"""
Vendor reverse-lookup for government meeting portals (CivicPlus, Legistar/Granicus, PrimeGov, Swagit).

Uses the same ``ddgs`` metasearch stack as ``enrichment/enrich_jurisdiction_websites_search.py`` (no paid
search API). Results are **raw search hits** for triangulation — not verified client lists.

Output (default)::

  data/cache/vendorsearch/_manifest.json
  data/cache/vendorsearch/hits.jsonl   # one JSON object per line

Modes:

- **global**: Broad ``site:`` and vendor-directory style queries (one pass per vendor family).
- **per-state**: For each USPS code, runs city- and county-oriented queries templated with the state name
  (heavy: ~51 × several queries; use ``--states`` to subset).

Examples (repo root)::

  .venv/bin/python scripts/datasources/vendorsearch/vendor_meeting_portal_search.py --mode global
  .venv/bin/python scripts/datasources/vendorsearch/vendor_meeting_portal_search.py --mode per-state --states TX CA
  .venv/bin/python scripts/datasources/vendorsearch/vendor_meeting_portal_search.py --vendor legistar --max-results 15 --sleep 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.datasources.uscm.state_names import STATE_FULL_NAME  # noqa: E402

CACHE_ROOT = REPO_ROOT / "data" / "cache" / "vendorsearch"


@dataclass(frozen=True)
class SearchTask:
    vendor_family: str
    scope: str  # "global" | "state"
    state_usps: str | None
    query: str


def _ddg_search(query: str, *, max_results: int, proxy: str | None) -> list[dict[str, Any]]:
    from ddgs import DDGS

    kwargs: dict[str, Any] = {"timeout": 30}
    if proxy:
        kwargs["proxy"] = proxy
    return list(DDGS(**kwargs).text(query, max_results=max_results))


def vendor_from_href(href: str) -> str | None:
    """Best-effort label from result URL (hit may be a blog or third party)."""
    try:
        host = urlparse(href).netloc.lower()
    except ValueError:
        return None
    if "legistar.com" in host:
        return "legistar"
    if "granicus.com" in host or "granicus-cdn" in host:
        return "granicus"
    if "civicplus.com" in host or "civicengage.com" in host:
        return "civicplus"
    if "primegov.com" in host:
        return "primegov"
    if "swagit.com" in host or "swagit.net" in host:
        return "swagit"
    if "civicclerk" in host:
        return "civicclerk"
    return None


def _global_queries() -> list[SearchTask]:
    rows: list[SearchTask] = []
    for q in (
        'site:civicplus.com "AgendaCenter"',
        'site:civicplus.com counties',
        'site:civicplus.com city council',
        'site:civicengage.com AgendaCenter',
        "CivicClerk government meetings",
    ):
        rows.append(SearchTask("civicplus", "global", None, q))
    for q in (
        "site:legistar.com Calendar",
        'site:legistar.com "View.ashx"',
        "site:granicus.com Subscribers.aspx",
        "site:granicus.com player",
        "Granicus Legistar county meetings",
    ):
        rows.append(SearchTask("legistar_granicus", "global", None, q))
    for q in (
        "site:primegov.com public portal meeting",
        "site:primegov.com /Portal/",
        "site:swagit.com /videos/",
        "site:swagit.com government channel",
    ):
        rows.append(SearchTask("primegov_swagit", "global", None, q))
    for q in (
        "site:legistar.com state legislature",
        "site:granicus.com state capitol meetings",
    ):
        rows.append(SearchTask("legistar_granicus", "global", None, q))
    return rows


def _per_state_queries(state_usps: str) -> list[SearchTask]:
    name = STATE_FULL_NAME[state_usps]
    st = state_usps
    return [
        SearchTask("civicplus", "state", st, f'{name} county site:civicplus.com AgendaCenter'),
        SearchTask("civicplus", "state", st, f'{name} city council site:civicplus.com'),
        SearchTask("civicplus", "state", st, f'{name} state government site:civicplus.com AgendaCenter'),
        SearchTask("legistar_granicus", "state", st, f'{name} county site:legistar.com'),
        SearchTask("legistar_granicus", "state", st, f'{name} city council site:legistar.com'),
        SearchTask("legistar_granicus", "state", st, f'{name} county granicus meetings'),
        SearchTask("legistar_granicus", "state", st, f'{name} state legislature site:legistar.com'),
        SearchTask("legistar_granicus", "state", st, f'{name} state board meetings granicus'),
        SearchTask("primegov_swagit", "state", st, f'{name} county site:primegov.com'),
        SearchTask("primegov_swagit", "state", st, f'{name} city site:swagit.com'),
    ]


def _tasks_for_args(
    *,
    mode: str,
    vendor: str,
    states: list[str],
) -> list[SearchTask]:
    global_q = _global_queries()
    per_st: list[SearchTask] = []
    for u in states:
        per_st.extend(_per_state_queries(u))

    def fam_ok(task: SearchTask) -> bool:
        if vendor == "all":
            return True
        if vendor == "civicplus":
            return task.vendor_family == "civicplus"
        if vendor in ("legistar", "granicus", "legistar_granicus"):
            return task.vendor_family == "legistar_granicus"
        if vendor in ("primegov", "swagit", "primegov_swagit"):
            return task.vendor_family == "primegov_swagit"
        return task.vendor_family == vendor

    out: list[SearchTask] = []
    if mode in ("global", "both"):
        out.extend(t for t in global_q if fam_ok(t))
    if mode in ("per-state", "both"):
        out.extend(t for t in per_st if fam_ok(t))
    return out


def _dedupe_key(href: str, query: str) -> str:
    return hashlib.sha256(f"{href}\n{query}".encode()).hexdigest()[:32]


def run_tasks(
    tasks: list[SearchTask],
    *,
    max_results: int,
    sleep_s: float,
    proxy: str | None,
) -> Iterator[dict[str, Any]]:
    seen: set[str] = set()
    n = len(tasks)
    for i, task in enumerate(tasks):
        logger.info("[{}/{}] {}", i + 1, n, task.query)
        try:
            raw = _ddg_search(task.query, max_results=max_results, proxy=proxy)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DDG failed for query={!r}: {}", task.query, exc)
            yield {
                "kind": "query_error",
                "vendor_family": task.vendor_family,
                "scope": task.scope,
                "state_usps": task.state_usps,
                "query": task.query,
                "error": str(exc),
            }
            time.sleep(sleep_s)
            continue

        for row in raw:
            href = (row.get("href") or "").strip()
            if not href:
                continue
            dk = _dedupe_key(href, task.query)
            if dk in seen:
                continue
            seen.add(dk)
            yield {
                "kind": "hit",
                "vendor_family": task.vendor_family,
                "vendor_inferred_from_url": vendor_from_href(href),
                "scope": task.scope,
                "state_usps": task.state_usps,
                "query": task.query,
                "title": (row.get("title") or "").strip(),
                "href": href,
                "body": (row.get("body") or "").strip(),
            }
        time.sleep(sleep_s)


def main() -> None:
    parser = argparse.ArgumentParser(description="DDG vendor reverse-lookup snapshots for meeting portals.")
    parser.add_argument(
        "--mode",
        choices=("global", "per-state", "both"),
        default="global",
        help="global = vendor-wide queries; per-state = city/county queries per state; both = union",
    )
    parser.add_argument(
        "--vendor",
        default="all",
        choices=(
            "all",
            "civicplus",
            "legistar",
            "granicus",
            "legistar_granicus",
            "primegov",
            "swagit",
            "primegov_swagit",
        ),
        help="Filter task families (legistar/granicus share one query set)",
    )
    parser.add_argument(
        "--states",
        default="",
        help="Comma USPS codes for --mode per-state or both (default: all 50 + DC)",
    )
    parser.add_argument("--max-results", type=int, default=12, help="Max DDG results per query")
    parser.add_argument("--sleep", type=float, default=2.0, help="Seconds between queries")
    parser.add_argument("--proxy", default=None, help="Optional proxy URL for DDG (e.g. socks5h://...)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=f"Output directory (default: {CACHE_ROOT})",
    )
    args = parser.parse_args()

    states = [x.strip().upper() for x in args.states.split(",") if x.strip()]
    if not states:
        states = sorted(STATE_FULL_NAME.keys())

    bad = [s for s in states if s not in STATE_FULL_NAME]
    if bad:
        raise SystemExit(f"Unknown state code(s): {bad}")

    tasks = _tasks_for_args(mode=args.mode, vendor=args.vendor, states=states)
    if not tasks:
        raise SystemExit("No tasks after filters — check --mode and --vendor")

    out_dir = (args.out_dir or CACHE_ROOT).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    hits_path = out_dir / "hits.jsonl"
    manifest_path = out_dir / "_manifest.json"

    try:
        cache_rel = str(out_dir.relative_to(REPO_ROOT))
    except ValueError:
        cache_rel = str(out_dir)
    try:
        hits_rel = str(hits_path.relative_to(REPO_ROOT))
    except ValueError:
        hits_rel = str(hits_path)

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "vendor": args.vendor,
        "states": states if args.mode in ("per-state", "both") else [],
        "max_results": args.max_results,
        "sleep_seconds": args.sleep,
        "task_count": len(tasks),
        "cache_root": cache_rel,
        "hits_jsonl": hits_rel,
        "notes": (
            "Raw DDG hits for manual triangulation; vendor_inferred_from_url is host-based heuristics only."
        ),
    }

    hit_count = 0
    err_count = 0
    row_n = 0
    with hits_path.open("w", encoding="utf-8") as f:
        for row in run_tasks(tasks, max_results=args.max_results, sleep_s=args.sleep, proxy=args.proxy):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            row_n += 1
            if row.get("kind") == "hit":
                hit_count += 1
            elif row.get("kind") == "query_error":
                err_count += 1
            if row_n % 200 == 0:
                logger.info("... {} rows written", row_n)

    manifest["hit_rows"] = hit_count
    manifest["query_error_rows"] = err_count
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Wrote {} hits (+ {} errors) to {}", hit_count, err_count, hits_path)
    logger.info("Manifest: {}", manifest_path)


if __name__ == "__main__":
    main()
