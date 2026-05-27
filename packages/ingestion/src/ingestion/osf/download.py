#!/usr/bin/env python3
"""
OSF ZIP Downloader + Extractor

Goal:
  - Download the dataset ZIP from an OSF "osfstorage" page
  - Extract into a stable cache folder:
      data/cache/osf/osf/

Usage:
  python scripts/datasources/osf/download_osf_zip.py
  python scripts/datasources/osf/download_osf_zip.py --page-url https://osf.io/mv5e6/files/osfstorage
  python scripts/datasources/osf/download_osf_zip.py --zip-url <direct-zip-url>
  python scripts/datasources/osf/download_osf_zip.py --force
  python scripts/datasources/osf/download_osf_zip.py --no-extract
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import zipfile
from pathlib import Path
import json
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from loguru import logger  # type: ignore
except Exception:  # pragma: no cover
    class _FallbackLogger:
        def info(self, msg: str) -> None:
            print(msg)

        def success(self, msg: str) -> None:
            print(msg)

        def warning(self, msg: str) -> None:
            print(msg)

        def error(self, msg: str) -> None:
            print(msg, file=sys.stderr)

    logger = _FallbackLogger()


DEFAULT_PAGE_URL = "https://osf.io/mv5e6/files/osfstorage"
DEFAULT_CACHE_DIR = Path("data/cache/osf")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_zip_response(final_url: str, content_type: str | None) -> bool:
    ct = (content_type or "").lower()
    if "application/zip" in ct:
        return True
    return final_url.lower().endswith(".zip")


def _fetch_text(url: str, timeout_s: int = 60) -> tuple[str, str | None]:
    """
    Fetch a URL and return (text, content_type). Uses stdlib to avoid extra deps.
    """
    req = Request(url, headers={"User-Agent": "open-navigator (osf downloader)"})
    with urlopen(req, timeout=timeout_s) as resp:
        ct = resp.headers.get("Content-Type")
        data = resp.read()
        # best-effort decode; OSF pages are UTF-8, but keep this robust
        text = data.decode("utf-8", errors="replace")
        return text, ct


def _fetch_json(url: str, timeout_s: int = 60) -> dict:
    req = Request(
        url,
        headers={
            "User-Agent": "open-navigator (osf downloader)",
            "Accept": "application/vnd.api+json",
        },
    )
    with urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8", errors="replace"))


def _discover_zip_url_via_osf_api(page_url: str) -> str | None:
    """
    Use OSF API to list files for a node/provider and find a .zip download link.

    Page URL pattern we expect:
      https://osf.io/<node_id>/files/<provider>
    """
    m = re.search(r"osf\.io/([A-Za-z0-9]{5})/files/([A-Za-z0-9_-]+)", page_url)
    if not m:
        return None
    node_id, provider = m.group(1), m.group(2)

    # BFS folders until we find a .zip file
    start = f"https://api.osf.io/v2/nodes/{node_id}/files/{provider}/?page[size]=100"
    queue: list[str] = [start]
    seen: set[str] = set()
    first_download: str | None = None

    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        payload = _fetch_json(url, timeout_s=60)
        for item in payload.get("data", []):
            attrs = item.get("attributes") or {}
            kind = attrs.get("kind")
            name = (attrs.get("name") or "").lower()
            content_type = (attrs.get("content_type") or "").lower()
            links = item.get("links") or {}
            dl = links.get("download")

            if kind == "file" and dl:
                if first_download is None:
                    first_download = dl
                if name.endswith(".zip") or "zip" in content_type:
                    return dl

            if kind == "folder":
                rel = (item.get("relationships") or {}).get("files") or {}
                related = (rel.get("links") or {}).get("related")
                if related:
                    # Sometimes OSF returns an object like {"href": "..."} instead of a string
                    if isinstance(related, dict):
                        related = related.get("href")
                    if not isinstance(related, str) or not related:
                        continue
                    # add page size to reduce pagination calls
                    if "page[size]" not in related:
                        related = related + ("&" if "?" in related else "?") + "page[size]=100"
                    queue.append(related)

        next_link = (payload.get("links") or {}).get("next")
        if next_link:
            queue.append(next_link)

    return first_download


def _list_files_via_osf_api(page_url: str) -> list[tuple[str, str]]:
    """
    Return a list of (rel_path, download_url) for all files under the page_url
    (recursively if it contains folders).
    """
    m = re.search(r"osf\.io/([A-Za-z0-9]{5})/files/([A-Za-z0-9_-]+)", page_url)
    if not m:
        return []
    node_id, provider = m.group(1), m.group(2)
    start = f"https://api.osf.io/v2/nodes/{node_id}/files/{provider}/?page[size]=100"

    queue: list[str] = [start]
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        payload = _fetch_json(url, timeout_s=60)
        for item in payload.get("data", []):
            attrs = item.get("attributes") or {}
            kind = attrs.get("kind")
            links = item.get("links") or {}
            dl = links.get("download")

            if kind == "file" and dl:
                # Prefer materialized_path if present (keeps folder structure)
                rel = attrs.get("materialized_path") or attrs.get("path") or attrs.get("name") or "unknown"
                rel = str(rel).lstrip("/")
                if rel.endswith("/"):
                    rel = (attrs.get("name") or "unknown").lstrip("/")
                out.append((rel, dl))

            if kind == "folder":
                rel_files = (item.get("relationships") or {}).get("files") or {}
                related = (rel_files.get("links") or {}).get("related")
                if isinstance(related, dict):
                    related = related.get("href")
                if isinstance(related, str) and related:
                    if "page[size]" not in related:
                        related = related + ("&" if "?" in related else "?") + "page[size]=100"
                    queue.append(related)

        next_link = (payload.get("links") or {}).get("next")
        if next_link:
            queue.append(next_link)

    return out


def _discover_zip_url(page_url: str, html: str) -> str | None:
    """
    Heuristic: find a link that looks like a ZIP download.
    OSF often uses /download or ?action=download URLs.
    """
    candidates: list[str] = []

    # First: explicit .zip hrefs
    for m in re.finditer(r'href="([^"]+\.zip[^"]*)"', html, flags=re.IGNORECASE):
        candidates.append(m.group(1))

    # Second: "download" links near "zip"
    for m in re.finditer(r'href="([^"]+download[^"]*)"', html, flags=re.IGNORECASE):
        href = m.group(1)
        window_start = max(0, m.start() - 80)
        window_end = min(len(html), m.end() + 80)
        window = html[window_start:window_end].lower()
        if "zip" in window:
            candidates.append(href)

    # Third: any download link (fallback)
    if not candidates:
        for m in re.finditer(r'href="([^"]+download[^"]*)"', html, flags=re.IGNORECASE):
            candidates.append(m.group(1))

    # Normalize and prefer direct-looking ones
    normalized: list[str] = []
    for c in candidates:
        normalized.append(urljoin(page_url, c))

    # De-dupe while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for u in normalized:
        if u not in seen:
            seen.add(u)
            uniq.append(u)

    if not uniq:
        return None

    # Prefer .zip
    for u in uniq:
        if ".zip" in u.lower():
            return u

    # Prefer explicit download endpoint
    for u in uniq:
        if "download" in u.lower():
            return u

    return uniq[0]


def resolve_zip_url(page_url: str, zip_url: str | None) -> str:
    if zip_url:
        return zip_url

    logger.info(f"Fetching OSF page to discover zip link: {page_url}")
    html, ct = _fetch_text(page_url, timeout_s=60)
    if _looks_like_zip_response(page_url, ct):
        return page_url

    found = _discover_zip_url(page_url, html)
    if found:
        return found

    # Many OSF pages are JS-rendered; fall back to the OSF API.
    logger.info("HTML discovery failed; trying OSF API discovery…")
    api_found = _discover_zip_url_via_osf_api(page_url)
    if api_found:
        return api_found

    raise RuntimeError(
        "Could not discover a ZIP download link from the OSF page. "
        "Pass --zip-url with a direct ZIP URL."
    )


def download_zip(zip_url: str, dest: Path, force: bool) -> tuple[Path, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force and dest.stat().st_size > 1024:
        sha = _sha256_file(dest)
        logger.info(f"Using cached zip: {dest} (sha256={sha[:12]}...)")
        return dest, sha

    tmp = dest.with_suffix(".zip.part")
    if tmp.exists():
        tmp.unlink()

    logger.info(f"Downloading ZIP: {zip_url}")
    req = Request(zip_url, headers={"User-Agent": "open-navigator (osf downloader)"})
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urlopen(req, timeout=300) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                with tmp.open("wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total and downloaded % (20 * 1024 * 1024) < len(chunk):
                            logger.info(
                                f"  downloaded {downloaded / (1024**2):.0f} MB / {total / (1024**2):.0f} MB"
                            )
            last_err = None
            break
        except HTTPError as e:
            last_err = e
            # transient OSF errors do happen; retry a couple times
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                wait = 2 * attempt
                logger.warning(f"HTTP {e.code} from OSF (attempt {attempt}/3). Retrying in {wait}s…")
                time.sleep(wait)
                continue
            raise
        except URLError as e:
            last_err = e
            if attempt < 3:
                wait = 2 * attempt
                logger.warning(f"Network error (attempt {attempt}/3). Retrying in {wait}s…")
                time.sleep(wait)
                continue
            raise

    if last_err is not None:
        raise last_err

    tmp.replace(dest)
    sha = _sha256_file(dest)
    logger.success(f"Downloaded {dest} ({dest.stat().st_size / (1024**2):.1f} MB, sha256={sha[:12]}...)")
    return dest, sha


def extract_zip(zip_path: Path, extract_dir: Path, force: bool) -> int:
    extract_dir.mkdir(parents=True, exist_ok=True)

    marker = extract_dir / ".extracted_from_sha256"
    zip_sha = _sha256_file(zip_path)

    if marker.exists() and not force:
        if marker.read_text().strip() == zip_sha and any(extract_dir.iterdir()):
            logger.info(f"Using cached extraction: {extract_dir} (sha256={zip_sha[:12]}...)")
            return 0

    # Clean destination on force / changed zip
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Extracting {zip_path} → {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    marker.write_text(zip_sha)
    file_count = sum(1 for p in extract_dir.rglob("*") if p.is_file())
    logger.success(f"Extracted {file_count:,} files into {extract_dir}")
    return file_count


def _download_one(url: str, dest: Path, force: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    req = Request(url, headers={"User-Agent": "open-navigator (osf downloader)"})
    with urlopen(req, timeout=300) as resp:
        with tmp.open("wb") as f:
            shutil.copyfileobj(resp, f, length=1024 * 1024)
    tmp.replace(dest)


def download_all_files(page_url: str, extract_dir: Path, force: bool) -> int:
    files = _list_files_via_osf_api(page_url)
    if not files:
        raise RuntimeError("OSF API listing returned no files to download.")

    extract_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading {len(files):,} file(s) from OSF into {extract_dir} ...")

    n = 0
    for rel, dl in files:
        dest = extract_dir / rel
        _download_one(dl, dest, force=force)
        n += 1
    logger.success(f"Downloaded {n:,} files into {extract_dir}")
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OSF ZIP and extract into cache")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL, help="OSF osfstorage page URL")
    parser.add_argument("--zip-url", default=None, help="Direct ZIP URL (skip discovery)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Cache base directory")
    parser.add_argument("--force", action="store_true", help="Re-download and re-extract even if cached")
    parser.add_argument("--no-extract", action="store_true", help="Download only; do not extract")
    args = parser.parse_args()

    cache_dir: Path = args.cache_dir
    zip_path = cache_dir / "osf.zip"
    extract_dir = cache_dir / "osf"

    url = resolve_zip_url(args.page_url, args.zip_url)
    downloaded_zip, _sha = download_zip(url, zip_path, force=args.force)

    if args.no_extract:
        logger.info("--no-extract set; skipping unzip")
        return 0

    try:
        extract_zip(downloaded_zip, extract_dir, force=args.force)
    except zipfile.BadZipFile:
        logger.warning("Downloaded artifact was not a ZIP. Falling back to downloading all files via OSF API.")
        download_all_files(args.page_url, extract_dir, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())

