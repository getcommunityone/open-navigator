#!/usr/bin/env python3
"""
Download reference imagery from **Wikimedia Commons** only (no third-party sites).

Default output: ``data/cache/wikicommons/``.

1. **State / territory flags** — one hero file per USPS as ``{USPS}_colors_hero.{ext}`` from
   ``Category:SVG flags of states of the United States`` (direct ``File:`` members per state
   category; picks a canonical ``Flag of …`` SVG when possible).

2. **License plates** — recursive walk of ``Category:License plates of the United States by state``
   → ``{USPS}_{year}.{ext}`` plus ``{USPS}_latest.{ext}`` (same behavior as the earlier Commons-only export step).

Usage (repo root):

  python3 scripts/wikicommons/download_wikicommons_assets.py
  python3 scripts/wikicommons/download_wikicommons_assets.py --only AK TX
  python3 scripts/wikicommons/download_wikicommons_assets.py --skip-flags
  python3 scripts/wikicommons/download_wikicommons_assets.py --skip-plates
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

UA = "Mozilla/5.0 (compatible; OpenNavigatorWikiCommons/1.0; +https://github.com/getcommunityone/open-navigator-for-engagement)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_UA = UA + " (Wikimedia-Commons-assets)"

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


def _commons_api_get(params: dict[str, Any], sleep_s: float) -> dict[str, Any]:
    time.sleep(sleep_s)
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": COMMONS_UA,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _iter_category_members(
    cmtitle: str,
    cmtype: str,
    sleep_s: float,
) -> list[dict[str, Any]]:
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
        data = _commons_api_get(p, sleep_s)
        out.extend(data["query"]["categorymembers"])
        if "continue" not in data:
            break
        cont = {k: v for k, v in data["continue"].items()}
    return out


def _collect_file_titles_recursive(
    root_cat: str,
    sleep_s: float,
    seen_categories: set[str],
    acc: list[str],
) -> None:
    if root_cat in seen_categories:
        return
    seen_categories.add(root_cat)
    for m in _iter_category_members(root_cat, "file|subcat", sleep_s):
        t = m["title"]
        if t.startswith("Category:"):
            _collect_file_titles_recursive(t, sleep_s, seen_categories, acc)
        elif t.startswith("File:"):
            acc.append(t)


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


def _commons_fetch_binary(url: str, referer: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": COMMONS_UA,
            "Accept": "*/*",
            "Referer": referer,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _imageinfo_for_titles(
    titles: list[str],
    sleep_s: float,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i : i + 40]
        time.sleep(sleep_s)
        p = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "titles": "|".join(chunk),
            "iiprop": "url|timestamp|mime",
        }
        data = _commons_api_get(p, 0.0)
        for _pid, page in data["query"]["pages"].items():
            if page.get("missing"):
                continue
            ii = page.get("imageinfo")
            if not ii:
                continue
            out[page["title"]] = ii[0]
    return out


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


def download_commons_state_flags(
    out: Path,
    sleep_s: float,
    only_usps: set[str] | None,
) -> dict[str, Any]:
    """One ``{USPS}_colors_hero.svg`` (or other image ext) per area from per-state SVG flag categories."""
    by_usps: dict[str, Any] = {}

    for svg_short, usps in sorted(SVG_FLAGS_CAT_TO_USPS.items(), key=lambda kv: kv[1]):
        if only_usps is not None and usps not in only_usps:
            continue
        cat = f"Category:{svg_short}"
        files = [x["title"] for x in _iter_category_members(cat, "file", sleep_s) if x["title"].startswith("File:")]
        core = svg_short.removeprefix("SVG flags of ").strip()
        pick = _pick_canonical_flag_file(files, core)
        if not pick:
            by_usps[usps] = {
                "category": cat,
                "error": "No suitable Flag of … .svg file in category (or category missing).",
                "candidates": files[:12],
            }
            print(f"  Flags {usps}: SKIP (no canonical SVG)", file=sys.stderr)
            continue
        infos = _imageinfo_for_titles([pick], sleep_s)
        info = infos.get(pick)
        if not info or not info.get("url"):
            by_usps[usps] = {"category": cat, "error": "imageinfo missing", "file_title": pick}
            print(f"  Flags {usps}: SKIP (no imageinfo)", file=sys.stderr)
            continue
        mime = info.get("mime") or ""
        if not mime.startswith("image/"):
            by_usps[usps] = {"category": cat, "error": f"not an image ({mime})", "file_title": pick}
            continue
        ext = _ext_from_file_title(pick) or ".svg"
        fn = f"{usps}_colors_hero{ext}"
        dst = out / fn
        try:
            time.sleep(sleep_s)
            dst.write_bytes(_commons_fetch_binary(info["url"], FLAGS_INDEX_URL + "/"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            by_usps[usps] = {"category": cat, "error": str(e), "file_title": pick}
            print(f"  Flags {usps}: WARN {e}", file=sys.stderr)
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
        print(f"  Flags {usps} ← {pick}")

    return {
        "index_category_url": FLAGS_INDEX_URL,
        "by_usps": by_usps,
    }


def download_commons_license_plates(
    out: Path,
    sleep_s: float,
    only_usps: set[str] | None,
) -> dict[str, Any]:
    roots: list[tuple[str, str]] = []
    unmapped: list[str] = []
    for m in _iter_category_members(PLATES_PARENT, "subcat", sleep_s):
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
    for root_cat, usps in sorted(roots, key=lambda x: x[1]):
        seen_cats: set[str] = set()
        file_titles: list[str] = []
        _collect_file_titles_recursive(root_cat, sleep_s, seen_cats, file_titles)
        file_titles = list(dict.fromkeys(file_titles))
        if not file_titles:
            by_usps[usps] = {
                "root_category": root_cat,
                "files": [],
                "latest_filename": None,
                "note": "No files listed under this category tree.",
            }
            continue

        infos = _imageinfo_for_titles(file_titles, sleep_s)
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
            try:
                time.sleep(sleep_s)
                data = _commons_fetch_binary(r["url"], PLATES_PARENT_URL + "/")
                dst.write_bytes(data)
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
                print(f"  {usps} WARN: could not save {fn} from {r['file_title']}: {e}", file=sys.stderr)
                continue
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

        by_usps[usps] = {
            "root_category": root_cat,
            "latest_filename": latest_fn,
            "files": saved,
        }
        print(f"  Plates {usps}: {len(saved)} files → latest {latest_fn or '—'}")

    return {
        "parent_category_url": PLATES_PARENT_URL,
        "parent_category": PLATES_PARENT,
        "unmapped_subcategories": [u.removeprefix("Category:") for u in unmapped],
        "by_usps": by_usps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/cache/wikicommons"),
        help="Output directory (default: data/cache/wikicommons)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.85,
        help="Seconds between HTTP requests (default: 0.85)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="USPS",
        help="Only these USPS codes (e.g. AL TX DC PR).",
    )
    parser.add_argument(
        "--skip-flags",
        action="store_true",
        help="Skip SVG state flag heroes.",
    )
    parser.add_argument(
        "--skip-plates",
        action="store_true",
        help="Skip license plate downloads.",
    )
    args = parser.parse_args()
    out: Path = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    only = {u.upper() for u in args.only} if args.only else None

    flags_manifest: dict[str, Any] | None = None
    plates_manifest: dict[str, Any] | None = None

    if not args.skip_flags:
        print("Downloading Wikimedia Commons SVG state flags …", flush=True)
        flags_manifest = download_commons_state_flags(out, args.sleep, only)

    if not args.skip_plates:
        print("Downloading Wikimedia Commons license plates …", flush=True)
        plates_manifest = download_commons_license_plates(out, args.sleep, only)

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

    mpath = out / "_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {mpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
