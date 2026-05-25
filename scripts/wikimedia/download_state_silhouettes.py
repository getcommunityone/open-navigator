#!/usr/bin/env python3
"""
Download U.S. state silhouette SVGs from Wikimedia Commons into ``data/cache/wikimedia/``.

Resolution order per state:
1. ``File:State of {StateName}.svg`` when it is a real outline SVG (not a redirect to a seal/flag).
2. ``File:Map of USA {USPS}.svg`` — complete 50-state fallback series on Commons.

Usage (repo root):

  python3 scripts/wikimedia/download_state_silhouettes.py
  python3 scripts/wikimedia/download_state_silhouettes.py --only GA TX
  python3 scripts/wikimedia/download_state_silhouettes.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
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


def _resolve_title(usps: str, name: str, infos: dict[str, dict[str, Any]]) -> tuple[str, str] | None:
    primary = f"File:State of {name}.svg"
    fallback = f"File:Map of USA {usps}.svg"
    primary_info = infos.get(primary)
    if primary_info and _is_valid_silhouette(primary, primary_info):
        page_title = primary_info.get("_page_title", primary)
        return page_title, "state_of"
    fallback_info = infos.get(fallback)
    if fallback_info and fallback_info.get("mime") == "image/svg+xml":
        page_title = fallback_info.get("_page_title", fallback)
        return page_title, "map_of_usa"
    return None


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
        "files": {},
    }
    ok = 0
    for usps, name in selected:
        resolved = _resolve_title(usps, name, infos)
        if not resolved:
            manifest["files"][usps] = {
                "state_name": name,
                "error": "No suitable silhouette SVG found on Commons.",
            }
            print(f"  {usps}: SKIP (no file)", file=sys.stderr)
            continue

        file_title, strategy = resolved
        info = infos[file_title]
        url = info["url"]
        referer = info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(file_title.replace(' ', '_'))}"
        local_name = f"{usps}_silhouette.svg"
        dest = out_dir / local_name

        if dry_run:
            print(f"  {usps}: would download {file_title} -> {local_name} ({strategy})")
            ok += 1
            manifest["files"][usps] = {
                "state_name": name,
                "commons_title": file_title.replace("File:", ""),
                "commons_url": referer,
                "download_url": url,
                "strategy": strategy,
                "local_file": local_name,
                "dry_run": True,
            }
            continue

        try:
            body = _commons_fetch_binary(url, referer)
            dest.write_bytes(body)
        except Exception as exc:  # noqa: BLE001
            manifest["files"][usps] = {
                "state_name": name,
                "commons_title": file_title.replace("File:", ""),
                "error": str(exc),
            }
            print(f"  {usps}: FAIL ({exc})", file=sys.stderr)
            continue

        manifest["files"][usps] = {
            "state_name": name,
            "commons_title": file_title.replace("File:", ""),
            "commons_url": referer,
            "download_url": url,
            "strategy": strategy,
            "local_file": local_name,
            "bytes": len(body),
            "timestamp": info.get("timestamp"),
        }
        ok += 1
        print(f"  {usps}: {file_title.replace('File:', '')} -> {local_name} ({strategy})")
        time.sleep(sleep_s)

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
    args = parser.parse_args()
    only = {x.upper() for x in args.only} if args.only else None
    download_state_silhouettes(args.out, args.sleep, only, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
