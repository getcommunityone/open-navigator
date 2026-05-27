"""Download reference imagery from **Wikimedia Commons** into ``data/cache/wikicommons/``.

Ported from scripts/wikicommons/download_wikicommons_assets.py to
core_lib.http.BaseAsyncClient (retries, rate limiting, structured logs). This
module is DOWNLOAD-ONLY; the frontend-publish sync (scripts/frontend/sync_*.sh)
stays out of scope. The pure category/flag/plate helpers are preserved verbatim.

1. **State / territory flags** — one hero file per USPS as ``{USPS}_colors_hero.{ext}`` from
   per-state ``SVG flags of …`` categories (picks a canonical ``Flag of …`` SVG when possible).
2. **License plates** — recursive walk of ``Category:License plates of the United States by state``
   → ``{USPS}_{year}.{ext}`` plus ``{USPS}_latest.{ext}``.

Two Commons hosts are fetched, both via BaseAsyncClient with absolute URLs:
  * ``https://commons.wikimedia.org/w/api.php`` — categorymembers + imageinfo JSON queries.
  * ``https://upload.wikimedia.org/...`` — the image bytes (absolute ``url`` from imageinfo).

Usage:
    python -m ingestion.wikicommons.download
    python -m ingestion.wikicommons.download --only AK TX
    python -m ingestion.wikicommons.download --skip-flags
    python -m ingestion.wikicommons.download --skip-plates
    python -m ingestion.wikicommons.download --force
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any

from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


UA = "Mozilla/5.0 (compatible; OpenNavigatorWikiCommons/1.0; +https://github.com/getcommunityone/open-navigator-for-engagement)"
_COMMONS_BASE_URL = "https://commons.wikimedia.org"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_UA = UA + " (Wikimedia-Commons-assets)"

CACHE_DIR = Path("data/cache/wikicommons")
_MAX_CACHE_AGE_S = 7 * 24 * 60 * 60  # reuse a cache file younger than 7 days

FLAGS_INDEX_URL = "https://commons.wikimedia.org/wiki/Category:SVG_flags_of_states_of_the_United_States"

PLATES_PARENT = "Category:License plates of the United States by state"
PLATES_PARENT_URL = (
    "https://commons.wikimedia.org/wiki/Category:License_plates_of_the_United_States_by_state"
)

# Subcategory short title (no ``Category:``) → USPS (license plate category names).
_LICENSE_PLATE_CAT_TO_USPS: dict[str, str] = {
    "License plates of American Samoa": "AS",
    "License plates of the Canal Zone": "CZ",
    "License plates of Guam": "GU",
    "License plates of the Northern Mariana Islands": "MP",
    "License plates of Puerto Rico": "PR",
    "License plates of the United States Virgin Islands": "VI",
    "License plates of Washington, D.C.": "DC",
    "License plates of Alabama": "AL",
    "License plates of Alaska": "AK",
    "License plates of Arizona": "AZ",
    "License plates of Arkansas": "AR",
    "License plates of California": "CA",
    "License plates of Colorado": "CO",
    "License plates of Connecticut": "CT",
    "License plates of Delaware": "DE",
    "License plates of Florida": "FL",
    "License plates of Georgia (U.S. state)": "GA",
    "License plates of Hawaii": "HI",
    "License plates of Idaho": "ID",
    "License plates of Illinois": "IL",
    "License plates of Indiana": "IN",
    "License plates of Iowa": "IA",
    "License plates of Kansas": "KS",
    "License plates of Kentucky": "KY",
    "License plates of Louisiana": "LA",
    "License plates of Maine": "ME",
    "Vehicle registration plates of Maryland": "MD",
    "License plates of Massachusetts": "MA",
    "License plates of Michigan": "MI",
    "License plates of Minnesota": "MN",
    "License plates of Mississippi (state)": "MS",
    "Vehicle registration plates of Missouri": "MO",
    "License plates of Montana": "MT",
    "License plates of Nebraska": "NE",
    "License plates of Nevada": "NV",
    "License plates of New Hampshire": "NH",
    "License plates of New Jersey": "NJ",
    "License plates of New Mexico": "NM",
    "License plates of New York (state)": "NY",
    "License plates of North Carolina": "NC",
    "License plates of North Dakota": "ND",
    "License plates of Ohio": "OH",
    "License plates of Oklahoma": "OK",
    "License plates of Oregon": "OR",
    "License plates of Pennsylvania": "PA",
    "License plates of Rhode Island": "RI",
    "License plates of South Carolina": "SC",
    "License plates of South Dakota": "SD",
    "License plates of Tennessee": "TN",
    "License plates of Texas": "TX",
    "License plates of Utah": "UT",
    "License plates of Vermont": "VT",
    "License plates of Virginia": "VA",
    "License plates of Washington (state)": "WA",
    "License plates of West Virginia": "WV",
    "Vehicle registration plates of Wisconsin": "WI",
    "License plates of Wyoming": "WY",
}


def _plate_short_to_svg_flag_short(plate_short: str) -> str:
    if plate_short.startswith("Vehicle registration plates of "):
        rest = plate_short[len("Vehicle registration plates of ") :]
        return f"SVG flags of {rest}"
    if plate_short.startswith("License plates of "):
        rest = plate_short[len("License plates of ") :]
        return f"SVG flags of {rest}"
    return f"SVG flags of {plate_short}"


SVG_FLAGS_CAT_TO_USPS: dict[str, str] = {
    _plate_short_to_svg_flag_short(k): v for k, v in _LICENSE_PLATE_CAT_TO_USPS.items()
}

_PLATE_YEAR_RE = re.compile(r"\b(19\d{2}|20[0-3]\d)\b")

_FLAG_TITLE_BAD_SUBSTR = frozenset(
    {
        "nuvola",
        "alternate",
        "proposal",
        "historical",
        "covid",
        "construction",
        "governor",
        "burgee",
        "romania",
        "eurovision",
        "lares",
        "grito",
        "protest",
        "design proposal",
        "dar ",
        "sheet",
        "orb ",
        " (square)",
        " (1)",
        " (1938)",
        " (1924)",
    }
)


# ---------------------------------------------------------------------------
# Pure helpers (preserved verbatim from the original script)
# ---------------------------------------------------------------------------

def _ext_from_file_title(file_title: str) -> str:
    name = file_title.split(":", 1)[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def _flag_core_variants(core: str) -> list[str]:
    """Lowercase substrings a canonical state flag file should match (longest first)."""
    low = core.strip().lower()
    out: list[str] = []
    for s in (
        low,
        low.replace(" (state)", "").strip(),
        low.replace(" (u.s. state)", "").strip(),
    ):
        if s and s not in out:
            out.append(s)
    return out


def _pick_canonical_flag_file(file_titles: list[str], core: str) -> str | None:
    """Prefer ``Flag of …`` SVG whose filename reflects ``core`` (after ``SVG flags of ``)."""
    variants = _flag_core_variants(core)
    candidates: list[tuple[int, str]] = []
    for ft in file_titles:
        if not ft.lower().endswith(".svg"):
            continue
        base = ft.split(":", 1)[-1]
        low = base.lower()
        if not low.startswith("flag of "):
            continue
        if any(b in low for b in _FLAG_TITLE_BAD_SUBSTR):
            continue
        if "new york" in variants and "state" in core.lower() and "new york city" in low:
            continue
        if "washington" in variants and "(state)" in core.lower():
            if "d.c" in low or "district of columbia" in low:
                continue
        matched = False
        for v in variants:
            if v and v in low:
                matched = True
                break
        if not matched:
            continue
        candidates.append((len(base), ft))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _parse_ts(ts: str) -> dt.datetime:
    try:
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _plate_year_label(file_title: str, upload_ts: str) -> str:
    name = file_title.split(":", 1)[-1]
    years = [int(y) for y in _PLATE_YEAR_RE.findall(name)]
    plausible = [y for y in years if 1900 <= y <= 2039]
    if plausible:
        return str(max(plausible))
    if len(upload_ts) >= 4 and upload_ts[:4].isdigit():
        return upload_ts[:4]
    return "unknown"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (dt.datetime.now().timestamp() - path.stat().st_mtime) < _MAX_CACHE_AGE_S


# ---------------------------------------------------------------------------
# HTTP client (BaseAsyncClient subclass)
# ---------------------------------------------------------------------------

class WikiCommonsAssetsClient(BaseAsyncClient):
    """BaseAsyncClient for the Commons categorymembers/imageinfo API + image bytes.

    base_url is commons.wikimedia.org; the API endpoint and the
    upload.wikimedia.org binary URLs are different paths/hosts, so all requests
    pass absolute URLs to ``get()``. The rate limiter throttles the (potentially
    large) plate-download loop, replacing the original ``--sleep`` delays.
    """

    def __init__(self) -> None:
        super().__init__(
            HttpClientConfig(
                base_url=_COMMONS_BASE_URL,
                source="wikicommons",
                timeout_s=120.0,
                rate_limit_per_sec=2.0,  # courteous throttle across many plate fetches
                rate_limit_burst=2,
                default_headers={"User-Agent": COMMONS_UA, "Accept": "*/*"},
            )
        )

    async def _api_get(self, params: dict[str, Any]) -> dict[str, Any]:
        resp = await self.get(
            COMMONS_API, params=params, headers={"Accept": "application/json"}
        )
        return resp.json()

    async def iter_category_members(self, cmtitle: str, cmtype: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cont: dict[str, str] = {}
        while True:
            p: dict[str, Any] = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "list": "categorymembers",
                "cmtitle": cmtitle,
                "cmtype": cmtype,
                "cmlimit": "500",
            }
            p.update(cont)
            data = await self._api_get(p)
            out.extend(data["query"]["categorymembers"])
            if "continue" not in data:
                break
            cont = {k: v for k, v in data["continue"].items()}
        return out

    async def collect_file_titles_recursive(
        self, root_cat: str, seen_categories: set[str], acc: list[str]
    ) -> None:
        if root_cat in seen_categories:
            return
        seen_categories.add(root_cat)
        for m in await self.iter_category_members(root_cat, "file|subcat"):
            t = m["title"]
            if t.startswith("Category:"):
                await self.collect_file_titles_recursive(t, seen_categories, acc)
            elif t.startswith("File:"):
                acc.append(t)

    async def imageinfo_for_titles(self, titles: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(titles), 40):
            chunk = titles[i : i + 40]
            data = await self._api_get(
                {
                    "action": "query",
                    "format": "json",
                    "prop": "imageinfo",
                    "titles": "|".join(chunk),
                    "iiprop": "url|timestamp|mime",
                }
            )
            for _pid, page in data["query"]["pages"].items():
                if page.get("missing"):
                    continue
                ii = page.get("imageinfo")
                if not ii:
                    continue
                out[page["title"]] = ii[0]
        return out

    async def fetch_binary(self, url: str, referer: str) -> bytes:
        resp = await self.get(url, headers={"Referer": referer})
        return resp.content


# ---------------------------------------------------------------------------
# Download orchestration + cache freshness (mirrors ingestion.gsa.download)
# ---------------------------------------------------------------------------

async def download_commons_state_flags(
    client: WikiCommonsAssetsClient,
    out: Path,
    *,
    only_usps: set[str] | None,
    force: bool,
) -> tuple[dict[str, Any], list[Path]]:
    """One ``{USPS}_colors_hero.svg`` (or other image ext) per area from per-state SVG flag categories."""
    by_usps: dict[str, Any] = {}
    written: list[Path] = []
    bound = logger.bind(source="wikicommons")

    for svg_short, usps in sorted(SVG_FLAGS_CAT_TO_USPS.items(), key=lambda kv: kv[1]):
        if only_usps is not None and usps not in only_usps:
            continue
        cat = f"Category:{svg_short}"
        members = await client.iter_category_members(cat, "file")
        files = [x["title"] for x in members if x["title"].startswith("File:")]
        core = svg_short.removeprefix("SVG flags of ").strip()
        pick = _pick_canonical_flag_file(files, core)
        if not pick:
            by_usps[usps] = {
                "category": cat,
                "error": "No suitable Flag of … .svg file in category (or category missing).",
                "candidates": files[:12],
            }
            bound.warning(f"Flags {usps}: SKIP (no canonical SVG)")
            continue
        ext = _ext_from_file_title(pick) or ".svg"
        fn = f"{usps}_colors_hero{ext}"
        dst = out / fn

        if not force and _is_fresh(dst):
            bound.info(f"Flags {usps}: cache_hit {dst}")
            by_usps[usps] = {"filename": fn, "category": cat, "file_title": pick}
            written.append(dst)
            continue

        infos = await client.imageinfo_for_titles([pick])
        info = infos.get(pick)
        if not info or not info.get("url"):
            by_usps[usps] = {"category": cat, "error": "imageinfo missing", "file_title": pick}
            bound.warning(f"Flags {usps}: SKIP (no imageinfo)")
            continue
        mime = info.get("mime") or ""
        if not mime.startswith("image/"):
            by_usps[usps] = {"category": cat, "error": f"not an image ({mime})", "file_title": pick}
            continue
        try:
            dst.write_bytes(await client.fetch_binary(info["url"], FLAGS_INDEX_URL + "/"))
        except Exception as e:  # noqa: BLE001
            by_usps[usps] = {"category": cat, "error": str(e), "file_title": pick}
            bound.warning(f"Flags {usps}: WARN {e}")
            continue
        wiki_title = pick.replace(" ", "_")
        by_usps[usps] = {
            "filename": fn,
            "category": cat,
            "commons_file_page": "https://commons.wikimedia.org/wiki/"
            + urllib.parse.quote(wiki_title, safe="/:"),
            "url": info["url"],
            "mime": mime,
            "upload_timestamp": info.get("timestamp"),
        }
        written.append(dst)
        bound.info(f"Flags {usps} <- {pick}")

    return {"index_category_url": FLAGS_INDEX_URL, "by_usps": by_usps}, written


async def download_commons_license_plates(
    client: WikiCommonsAssetsClient,
    out: Path,
    *,
    only_usps: set[str] | None,
    force: bool,
) -> tuple[dict[str, Any], list[Path]]:
    bound = logger.bind(source="wikicommons")
    roots: list[tuple[str, str]] = []
    unmapped: list[str] = []
    for m in await client.iter_category_members(PLATES_PARENT, "subcat"):
        t = m["title"]
        short = t.removeprefix("Category:")
        usps = _LICENSE_PLATE_CAT_TO_USPS.get(short)
        if usps is None:
            unmapped.append(t)
            continue
        if only_usps is not None and usps not in only_usps:
            continue
        roots.append((t, usps))

    by_usps: dict[str, Any] = {}
    written: list[Path] = []
    for root_cat, usps in sorted(roots, key=lambda x: x[1]):
        seen_cats: set[str] = set()
        file_titles: list[str] = []
        await client.collect_file_titles_recursive(root_cat, seen_cats, file_titles)
        file_titles = list(dict.fromkeys(file_titles))
        if not file_titles:
            by_usps[usps] = {
                "root_category": root_cat,
                "files": [],
                "latest_filename": None,
                "note": "No files listed under this category tree.",
            }
            continue

        infos = await client.imageinfo_for_titles(file_titles)
        rows: list[dict[str, Any]] = []
        for ft in file_titles:
            info = infos.get(ft)
            if not info:
                continue
            mime = info.get("mime") or ""
            if not mime.startswith("image/"):
                continue
            url = info.get("url")
            ts = info.get("timestamp") or ""
            if not url or not ts:
                continue
            year = _plate_year_label(ft, ts)
            ext = _ext_from_file_title(ft)
            if not ext:
                ext = ".jpg"
            rows.append(
                {
                    "file_title": ft,
                    "url": url,
                    "mime": mime,
                    "upload_timestamp": ts,
                    "year": year,
                    "ext": ext,
                }
            )

        used_names: dict[tuple[str, str], int] = {}
        saved: list[dict[str, Any]] = []
        best: tuple[tuple[int, dt.datetime], str, Path] | None = None

        for r in rows:
            year = r["year"]
            base = f"{usps}_{year}"
            key = (usps, year)
            n = used_names.get(key, 0)
            used_names[key] = n + 1
            stem = f"{base}_{n + 1}" if n > 0 else base
            fn = stem + r["ext"]
            dst = out / fn
            if not force and _is_fresh(dst):
                bound.info(f"  {usps} cache_hit {dst}")
            else:
                try:
                    data = await client.fetch_binary(r["url"], PLATES_PARENT_URL + "/")
                    dst.write_bytes(data)
                except Exception as e:  # noqa: BLE001
                    bound.warning(f"  {usps} WARN: could not save {fn} from {r['file_title']}: {e}")
                    continue
            written.append(dst)
            try:
                ysort = int(year) if year.isdigit() else 0
            except ValueError:
                ysort = 0
            tup_key = (ysort, _parse_ts(r["upload_timestamp"]))
            if best is None or tup_key > best[0]:
                best = (tup_key, r["ext"], dst)
            wiki_title = r["file_title"].replace(" ", "_")
            saved.append(
                {
                    "filename": fn,
                    "commons_file_page": "https://commons.wikimedia.org/wiki/"
                    + urllib.parse.quote(wiki_title, safe="/:"),
                    "url": r["url"],
                    "year": year,
                    "upload_timestamp": r["upload_timestamp"],
                }
            )

        latest_fn: str | None = None
        if best is not None:
            _, ext, src_path = best
            latest_fn = f"{usps}_latest{ext}"
            shutil.copyfile(src_path, out / latest_fn)
            written.append(out / latest_fn)

        by_usps[usps] = {
            "root_category": root_cat,
            "latest_filename": latest_fn,
            "files": saved,
        }
        bound.info(f"Plates {usps}: {len(saved)} files -> latest {latest_fn or '—'}")

    return {
        "parent_category_url": PLATES_PARENT_URL,
        "parent_category": PLATES_PARENT,
        "unmapped_subcategories": [u.removeprefix("Category:") for u in unmapped],
        "by_usps": by_usps,
    }, written


async def download(
    *,
    force: bool = False,
    only: set[str] | None = None,
    skip_flags: bool = False,
    skip_plates: bool = False,
) -> list[Path]:
    """Fetch Commons flags + license plates into the wikicommons cache.

    Reuses fresh cached files unless ``force``. Returns the list of cache Paths
    written (or reused). Mirrors the ingestion.gsa.download cache-freshness
    contract, per file.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    flags_manifest: dict[str, Any] | None = None
    plates_manifest: dict[str, Any] | None = None

    async with WikiCommonsAssetsClient() as client:
        if not skip_flags:
            logger.bind(source="wikicommons").info("Downloading Wikimedia Commons SVG state flags …")
            flags_manifest, paths = await download_commons_state_flags(
                client, CACHE_DIR, only_usps=only, force=force
            )
            written.extend(paths)
        if not skip_plates:
            logger.bind(source="wikicommons").info("Downloading Wikimedia Commons license plates …")
            plates_manifest, paths = await download_commons_license_plates(
                client, CACHE_DIR, only_usps=only, force=force
            )
            written.extend(paths)

    manifest: dict[str, Any] = {
        "source": "Wikimedia Commons only",
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attribution": (
            "Wikimedia Commons contributors; see each file page for authorship and license "
            "(typically CC BY-SA). Local cache for documentation and design reference."
        ),
    }
    if flags_manifest is not None:
        manifest["commons_state_flags"] = flags_manifest
    if plates_manifest is not None:
        manifest["commons_license_plates"] = plates_manifest

    mpath = CACHE_DIR / "_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    written.append(mpath)
    logger.bind(source="wikicommons").info(f"Wrote {mpath}")
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Wikimedia Commons flags + license plates into data/cache/wikicommons/"
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="USPS",
        help="Only these USPS codes (e.g. AL TX DC PR).",
    )
    parser.add_argument("--skip-flags", action="store_true", help="Skip SVG state flag heroes.")
    parser.add_argument("--skip-plates", action="store_true", help="Skip license plate downloads.")
    parser.add_argument("--force", action="store_true", help="Re-download even if a fresh cache exists")
    return parser


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    only = {u.upper() for u in args.only} if args.only else None
    paths = asyncio.run(
        download(force=args.force, only=only, skip_flags=args.skip_flags, skip_plates=args.skip_plates)
    )
    logger.info(f"wikicommons cache: {len(paths)} file(s) written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
