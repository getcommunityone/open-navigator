#!/usr/bin/env python3
"""
Download U.S. state silhouette SVGs from Wikimedia Commons into ``data/cache/wikimedia/``.

For each state we fetch **both** Commons variants when available:

1. **Locator** — ``File:Map of USA {USPS}.svg`` (state highlighted on the U.S. map).
   Saved as ``{USPS}_silhouette_locator.svg``. This is the UX default.
2. **State outline** — ``File:State of {StateName}.svg`` when it is a real outline SVG
   (not a redirect to a seal/flag). Saved as ``{USPS}_silhouette_state.svg``.

``{USPS}_silhouette.svg`` is a copy of the locator file when present, else the state
outline, for backward compatibility with older sync paths.

Usage (repo root):

  python3 scripts/wikimedia/download_state_silhouettes.py
  python3 scripts/wikimedia/download_state_silhouettes.py --only GA TX
  python3 scripts/wikimedia/download_state_silhouettes.py --dry-run
  python3 scripts/wikimedia/download_state_silhouettes.py --us-only
"""
from __future__ import annotations

import argparse
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

UA = (
    "Mozilla/5.0 (compatible; OpenNavigatorWikiSilhouettes/1.0; "
    "+https://github.com/getcommunityone/open-navigator-for-engagement)"
)
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _commons_api_get(params: dict[str, Any], sleep_s: float) -> dict[str, Any]:
    time.sleep(sleep_s)
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                time.sleep(3.0 + attempt * 2.0)
                continue
            raise
    raise RuntimeError("unreachable")


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


def _imageinfo_for_titles(
    titles: list[str],
    sleep_s: float,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i : i + 40]
        data = _commons_api_get(
            {
                "action": "query",
                "format": "json",
                "redirects": "1",
                "prop": "imageinfo",
                "titles": "|".join(chunk),
                "iiprop": "url|timestamp|mime|descriptionurl",
            },
            sleep_s if i == 0 else 0.85,
        )
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


def _commons_fetch_binary(url: str, referer: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*", "Referer": referer},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


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
    referer = info.get("descriptionurl") or (
        "https://commons.wikimedia.org/wiki/"
        + urllib.parse.quote(file_title.replace(" ", "_"))
    )
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


def _download_variant(
    out_dir: Path,
    *,
    usps: str,
    file_title: str,
    info: dict[str, Any],
    strategy: str,
    local_name: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    url = info["url"]
    referer = info.get("descriptionurl") or (
        "https://commons.wikimedia.org/wiki/"
        + urllib.parse.quote(file_title.replace(" ", "_"))
    )
    dest = out_dir / local_name

    if dry_run:
        print(
            f"  {usps}: would download {file_title.replace('File:', '')} "
            f"-> {local_name} ({strategy})"
        )
        return _variant_meta(
            file_title,
            info,
            strategy=strategy,
            local_file=local_name,
            dry_run=True,
        )

    try:
        body = _commons_fetch_binary(url, referer)
        dest.write_bytes(body)
    except Exception as exc:  # noqa: BLE001
        print(f"  {usps}: FAIL {local_name} ({exc})", file=sys.stderr)
        return None

    print(
        f"  {usps}: {file_title.replace('File:', '')} -> {local_name} ({strategy})"
    )
    return _variant_meta(
        file_title,
        info,
        strategy=strategy,
        local_file=local_name,
        body_len=len(body),
    )


def download_us_silhouette(
    out_dir: Path,
    sleep_s: float,
    dry_run: bool,
) -> bool:
    """Download the contiguous + AK/HI U.S. outline used as the national hero default."""
    out_dir.mkdir(parents=True, exist_ok=True)
    infos = _imageinfo_for_titles([US_SILHOUETTE_COMMONS], sleep_s)
    info = infos.get(US_SILHOUETTE_COMMONS)
    if not info or info.get("mime") != "image/svg+xml":
        print(f"  US: SKIP ({US_SILHOUETTE_COMMONS} not found)", file=sys.stderr)
        return False

    url = info["url"]
    referer = info.get("descriptionurl") or (
        "https://commons.wikimedia.org/wiki/"
        + urllib.parse.quote(US_SILHOUETTE_COMMONS.replace(" ", "_"))
    )
    dest = out_dir / US_SILHOUETTE_LOCAL

    if dry_run:
        print(f"  US: would download {US_SILHOUETTE_COMMONS} -> {US_SILHOUETTE_LOCAL}")
        return True

    try:
        body = _commons_fetch_binary(url, referer)
        dest.write_bytes(body)
    except Exception as exc:  # noqa: BLE001
        print(f"  US: FAIL ({exc})", file=sys.stderr)
        return False

    print(f"  US: {US_SILHOUETTE_COMMONS.replace('File:', '')} -> {US_SILHOUETTE_LOCAL}")
    time.sleep(sleep_s)
    return True


def download_state_silhouettes(
    out_dir: Path,
    sleep_s: float,
    only_usps: set[str] | None,
    dry_run: bool,
) -> dict[str, Any]:
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

    print(f"Resolving {len(unique_titles)} Commons file title(s)...")
    infos = _imageinfo_for_titles(unique_titles, sleep_s)

    manifest: dict[str, Any] = {
        "source": "Wikimedia Commons",
        "default_variant": "locator",
        "files": {},
    }
    ok = 0
    for usps, name in selected:
        entry: dict[str, Any] = {"state_name": name, "variants": {}}
        locator_resolved = _resolve_locator_title(usps, infos)
        state_resolved = _resolve_state_title(name, infos)

        if not locator_resolved and not state_resolved:
            entry["error"] = "No suitable silhouette SVG found on Commons."
            manifest["files"][usps] = entry
            print(f"  {usps}: SKIP (no file)", file=sys.stderr)
            continue

        if locator_resolved:
            file_title, strategy = locator_resolved
            meta = _download_variant(
                out_dir,
                usps=usps,
                file_title=file_title,
                info=infos[file_title],
                strategy=strategy,
                local_name=f"{usps}_silhouette_locator.svg",
                dry_run=dry_run,
            )
            if meta:
                entry["variants"]["locator"] = meta
                if not dry_run:
                    time.sleep(sleep_s)

        if state_resolved:
            file_title, strategy = state_resolved
            meta = _download_variant(
                out_dir,
                usps=usps,
                file_title=file_title,
                info=infos[file_title],
                strategy=strategy,
                local_name=f"{usps}_silhouette_state.svg",
                dry_run=dry_run,
            )
            if meta:
                entry["variants"]["state"] = meta
                if not dry_run:
                    time.sleep(sleep_s)

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

        manifest["files"][usps] = entry
        ok += 1

    manifest_path = out_dir / "_manifest.json"
    if not dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {manifest_path}")

    print(f"Done: {ok}/{len(selected)} state silhouette(s)")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=_repo_root() / "data/cache/wikimedia",
        help="Output directory (default: data/cache/wikimedia)",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="USPS",
        help="Limit to these USPS codes (e.g. GA TX)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between Commons API / download requests",
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
    args = parser.parse_args()
    only = {x.upper() for x in args.only} if args.only else None
    if args.us_only:
        download_us_silhouette(args.out, args.sleep, args.dry_run)
        return 0
    if not args.no_us:
        download_us_silhouette(args.out, args.sleep, args.dry_run)
    if not args.us_only:
        download_state_silhouettes(args.out, args.sleep, only, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
