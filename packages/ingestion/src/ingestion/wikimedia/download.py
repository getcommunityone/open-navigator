"""Download U.S. state silhouette SVGs from Wikimedia Commons into ``data/cache/wikimedia/``.

Ported from scripts/wikimedia/download_state_silhouettes.py to
core_lib.http.BaseAsyncClient (retries, rate limiting, structured logs). This
module is DOWNLOAD-ONLY; the frontend-publish sync (scripts/frontend/sync_*.sh)
stays out of scope. The pure title-resolution / validation helpers are preserved
verbatim from the original script.

For each state we fetch **both** Commons variants when available:

1. **Locator** — ``File:Map of USA {USPS}.svg`` (state highlighted on the U.S. map).
   Saved as ``{USPS}_silhouette_locator.svg``. This is the UX default.
2. **State outline** — ``File:State of {StateName}.svg`` when it is a real outline SVG
   (not a redirect to a seal/flag). Saved as ``{USPS}_silhouette_state.svg``.

``{USPS}_silhouette.svg`` is a copy of the locator file when present, else the state
outline, for backward compatibility with older sync paths.

Two Commons hosts are fetched, both via the BaseAsyncClient with absolute URLs:
  * ``https://commons.wikimedia.org/w/api.php`` — imageinfo JSON queries.
  * ``https://upload.wikimedia.org/...`` — the SVG bytes (absolute ``url`` from imageinfo).

Usage:
    python -m ingestion.wikimedia.download
    python -m ingestion.wikimedia.download --only GA TX
    python -m ingestion.wikimedia.download --dry-run
    python -m ingestion.wikimedia.download --us-only
    python -m ingestion.wikimedia.download --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


UA = (
    "Mozilla/5.0 (compatible; OpenNavigatorWikiSilhouettes/1.0; "
    "+https://github.com/getcommunityone/open-navigator-for-engagement)"
)
_COMMONS_BASE_URL = "https://commons.wikimedia.org"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

CACHE_DIR = Path("data/cache/wikimedia")
_MAX_CACHE_AGE_S = 7 * 24 * 60 * 60  # reuse a cache file younger than 7 days

# National default for hero when no state is selected (not a USPS code).
US_SILHOUETTE_COMMONS = "File:United States of America.svg"
US_SILHOUETTE_LOCAL = "USA_silhouette.svg"

STATES: list[tuple[str, str]] = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]

_BAD_SUBSTR = frozenset(
    {
        "seal",
        "flag",
        "coat of arms",
        "emblem",
        "logo",
        "burgee",
        "motto",
    }
)


# ---------------------------------------------------------------------------
# Pure helpers (preserved verbatim from the original script)
# ---------------------------------------------------------------------------

def _slug(title: str) -> str:
    return re.sub(r"\s+", "_", title.strip())


def _is_valid_silhouette(file_title: str, info: dict[str, Any]) -> bool:
    if info.get("mime") != "image/svg+xml":
        return False
    base = file_title.split(":", 1)[-1]
    low = base.lower()
    if any(b in low for b in _BAD_SUBSTR):
        return False
    url = (info.get("url") or "").lower()
    desc = (info.get("descriptionurl") or "").lower()
    if any(b in url for b in _BAD_SUBSTR) or any(b in desc for b in _BAD_SUBSTR):
        return False
    expected = _slug(base).lower()
    if expected not in url and expected not in desc:
        return False
    return True


def _resolve_locator_title(
    usps: str, infos: dict[str, dict[str, Any]]
) -> tuple[str, str] | None:
    fallback = f"File:Map of USA {usps}.svg"
    fallback_info = infos.get(fallback)
    if fallback_info and fallback_info.get("mime") == "image/svg+xml":
        page_title = fallback_info.get("_page_title", fallback)
        return page_title, "map_of_usa"
    return None


def _resolve_state_title(
    name: str, infos: dict[str, dict[str, Any]]
) -> tuple[str, str] | None:
    primary = f"File:State of {name}.svg"
    primary_info = infos.get(primary)
    if primary_info and _is_valid_silhouette(primary, primary_info):
        page_title = primary_info.get("_page_title", primary)
        return page_title, "state_of"
    return None


def _variant_meta(
    file_title: str,
    info: dict[str, Any],
    *,
    strategy: str,
    local_file: str,
    body_len: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    referer = _referer_for(file_title, info)
    meta: dict[str, Any] = {
        "commons_title": file_title.replace("File:", ""),
        "commons_url": referer,
        "download_url": info["url"],
        "strategy": strategy,
        "local_file": local_file,
        "timestamp": info.get("timestamp"),
    }
    if dry_run:
        meta["dry_run"] = True
    elif body_len is not None:
        meta["bytes"] = body_len
    return meta


def _referer_for(file_title: str, info: dict[str, Any]) -> str:
    return info.get("descriptionurl") or (
        "https://commons.wikimedia.org/wiki/"
        + urllib.parse.quote(file_title.replace(" ", "_"))
    )


def _is_fresh(path: Path) -> bool:
    return path.exists() and (datetime.now().timestamp() - path.stat().st_mtime) < _MAX_CACHE_AGE_S


# ---------------------------------------------------------------------------
# HTTP client (BaseAsyncClient subclass)
# ---------------------------------------------------------------------------

class WikimediaSilhouettesClient(BaseAsyncClient):
    """BaseAsyncClient for the Commons imageinfo API + upload.wikimedia.org bytes.

    base_url is the commons.wikimedia.org host; the imageinfo API endpoint and the
    upload.wikimedia.org binary URLs are different paths/hosts, so all requests
    pass absolute URLs to ``get()``. The rate limiter throttles the per-file loop.
    """

    def __init__(self) -> None:
        super().__init__(
            HttpClientConfig(
                base_url=_COMMONS_BASE_URL,
                source="wikimedia",
                timeout_s=120.0,
                rate_limit_per_sec=2.0,  # courteous throttle across many asset fetches
                rate_limit_burst=2,
                default_headers={"User-Agent": UA, "Accept": "*/*"},
            )
        )

    async def imageinfo_for_titles(self, titles: list[str]) -> dict[str, dict[str, Any]]:
        """Resolve imageinfo (url/mime/timestamp) for Commons file titles, chunked by 40."""
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(titles), 40):
            chunk = titles[i : i + 40]
            resp = await self.get(
                COMMONS_API,
                params={
                    "action": "query",
                    "format": "json",
                    "redirects": "1",
                    "prop": "imageinfo",
                    "titles": "|".join(chunk),
                    "iiprop": "url|timestamp|mime|descriptionurl",
                },
                headers={"Accept": "application/json"},
            )
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for _pid, page in pages.items():
                if page.get("missing"):
                    continue
                ii = (page.get("imageinfo") or [None])[0]
                if ii:
                    out[page["title"]] = {**ii, "_page_title": page["title"]}
            for redirect in data.get("query", {}).get("redirects", []):
                src = redirect.get("from")
                dst = redirect.get("to")
                if src and dst and dst in out and src not in out:
                    out[src] = out[dst]
        return out

    async def fetch_binary(self, url: str, referer: str) -> bytes:
        resp = await self.get(url, headers={"Referer": referer})
        return resp.content


# ---------------------------------------------------------------------------
# Download orchestration + cache freshness (mirrors ingestion.gsa.download)
# ---------------------------------------------------------------------------

async def _download_variant(
    client: WikimediaSilhouettesClient,
    out_dir: Path,
    *,
    usps: str,
    file_title: str,
    info: dict[str, Any],
    strategy: str,
    local_name: str,
    force: bool,
    dry_run: bool,
) -> tuple[dict[str, Any] | None, Path | None]:
    dest = out_dir / local_name
    bound = logger.bind(source="wikimedia", usps=usps)

    if dry_run:
        bound.info(f"would download {file_title.replace('File:', '')} -> {local_name} ({strategy})")
        return (
            _variant_meta(file_title, info, strategy=strategy, local_file=local_name, dry_run=True),
            None,
        )

    if not force and _is_fresh(dest):
        bound.info(f"cache_hit {dest}")
        return (
            _variant_meta(file_title, info, strategy=strategy, local_file=local_name,
                          body_len=dest.stat().st_size),
            dest,
        )

    referer = _referer_for(file_title, info)
    try:
        body = await client.fetch_binary(info["url"], referer)
        dest.write_bytes(body)
    except Exception as exc:  # noqa: BLE001
        bound.warning(f"FAIL {local_name} ({exc})")
        return None, None

    bound.info(f"{file_title.replace('File:', '')} -> {local_name} ({strategy})")
    return (
        _variant_meta(file_title, info, strategy=strategy, local_file=local_name, body_len=len(body)),
        dest,
    )


async def download_us_silhouette(
    client: WikimediaSilhouettesClient,
    out_dir: Path,
    *,
    force: bool,
    dry_run: bool,
) -> Path | None:
    """Download the contiguous + AK/HI U.S. outline used as the national hero default."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bound = logger.bind(source="wikimedia", usps="US")
    dest = out_dir / US_SILHOUETTE_LOCAL

    if not dry_run and not force and _is_fresh(dest):
        bound.info(f"cache_hit {dest}")
        return dest

    infos = await client.imageinfo_for_titles([US_SILHOUETTE_COMMONS])
    info = infos.get(US_SILHOUETTE_COMMONS)
    if not info or info.get("mime") != "image/svg+xml":
        bound.warning(f"SKIP ({US_SILHOUETTE_COMMONS} not found)")
        return None

    if dry_run:
        bound.info(f"would download {US_SILHOUETTE_COMMONS} -> {US_SILHOUETTE_LOCAL}")
        return None

    referer = _referer_for(US_SILHOUETTE_COMMONS, info)
    try:
        body = await client.fetch_binary(info["url"], referer)
        dest.write_bytes(body)
    except Exception as exc:  # noqa: BLE001
        bound.warning(f"FAIL ({exc})")
        return None

    bound.info(f"{US_SILHOUETTE_COMMONS.replace('File:', '')} -> {US_SILHOUETTE_LOCAL}")
    return dest


async def download_state_silhouettes(
    client: WikimediaSilhouettesClient,
    out_dir: Path,
    *,
    only_usps: set[str] | None,
    force: bool,
    dry_run: bool,
) -> tuple[dict[str, Any], list[Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = [(c, n) for c, n in STATES if only_usps is None or c in only_usps]

    titles: list[str] = []
    for usps, name in selected:
        titles.append(f"File:State of {name}.svg")
        titles.append(f"File:Map of USA {usps}.svg")

    seen: set[str] = set()
    unique_titles: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            unique_titles.append(t)

    bound = logger.bind(source="wikimedia")
    bound.info(f"Resolving {len(unique_titles)} Commons file title(s)...")
    infos = await client.imageinfo_for_titles(unique_titles)

    manifest: dict[str, Any] = {
        "source": "Wikimedia Commons",
        "default_variant": "locator",
        "files": {},
    }
    written: list[Path] = []
    ok = 0
    for usps, name in selected:
        entry: dict[str, Any] = {"state_name": name, "variants": {}}
        locator_resolved = _resolve_locator_title(usps, infos)
        state_resolved = _resolve_state_title(name, infos)

        if not locator_resolved and not state_resolved:
            entry["error"] = "No suitable silhouette SVG found on Commons."
            manifest["files"][usps] = entry
            bound.warning(f"{usps}: SKIP (no file)")
            continue

        if locator_resolved:
            file_title, strategy = locator_resolved
            meta, path = await _download_variant(
                client, out_dir, usps=usps, file_title=file_title, info=infos[file_title],
                strategy=strategy, local_name=f"{usps}_silhouette_locator.svg",
                force=force, dry_run=dry_run,
            )
            if meta:
                entry["variants"]["locator"] = meta
            if path:
                written.append(path)

        if state_resolved:
            file_title, strategy = state_resolved
            meta, path = await _download_variant(
                client, out_dir, usps=usps, file_title=file_title, info=infos[file_title],
                strategy=strategy, local_name=f"{usps}_silhouette_state.svg",
                force=force, dry_run=dry_run,
            )
            if meta:
                entry["variants"]["state"] = meta
            if path:
                written.append(path)

        if not entry["variants"]:
            entry["error"] = "Download failed for all variants."
            manifest["files"][usps] = entry
            continue

        default_local = (
            entry["variants"].get("locator", {}).get("local_file")
            or entry["variants"].get("state", {}).get("local_file")
        )
        entry["default_variant"] = (
            "locator" if "locator" in entry["variants"] else "state"
        )
        entry["local_file"] = default_local

        if not dry_run and default_local:
            legacy = out_dir / f"{usps}_silhouette.svg"
            shutil.copy2(out_dir / default_local, legacy)
            entry["legacy_local_file"] = legacy.name
            written.append(legacy)

        manifest["files"][usps] = entry
        ok += 1

    if not dry_run:
        manifest_path = out_dir / "_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        written.append(manifest_path)
        bound.info(f"Wrote {manifest_path}")

    bound.info(f"Done: {ok}/{len(selected)} state silhouette(s)")
    return manifest, written


async def download(
    *,
    force: bool = False,
    only: set[str] | None = None,
    dry_run: bool = False,
    us_only: bool = False,
    no_us: bool = False,
) -> list[Path]:
    """Fetch state silhouette SVGs into the wikimedia cache; reuse fresh files unless force.

    Returns the list of cache file Paths written (or reused). Mirrors the
    ingestion.gsa.download cache-freshness contract, per file.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    async with WikimediaSilhouettesClient() as client:
        if us_only:
            path = await download_us_silhouette(client, CACHE_DIR, force=force, dry_run=dry_run)
            if path:
                written.append(path)
            return written
        if not no_us:
            path = await download_us_silhouette(client, CACHE_DIR, force=force, dry_run=dry_run)
            if path:
                written.append(path)
        _manifest, state_paths = await download_state_silhouettes(
            client, CACHE_DIR, only_usps=only, force=force, dry_run=dry_run
        )
        written.extend(state_paths)
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download U.S. state silhouette SVGs from Wikimedia Commons into data/cache/wikimedia/"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="USPS",
        help="Limit to these USPS codes (e.g. GA TX)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve titles only; do not download or write manifest",
    )
    parser.add_argument(
        "--us-only",
        action="store_true",
        help=f"Download only {US_SILHOUETTE_LOCAL} ({US_SILHOUETTE_COMMONS})",
    )
    parser.add_argument(
        "--no-us",
        action="store_true",
        help="Skip national U.S. silhouette when downloading states",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if a fresh cache exists")
    return parser


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    only = {x.upper() for x in args.only} if args.only else None
    paths = asyncio.run(
        download(
            force=args.force,
            only=only,
            dry_run=args.dry_run,
            us_only=args.us_only,
            no_us=args.no_us,
        )
    )
    logger.info(f"wikimedia cache: {len(paths)} file(s) written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
