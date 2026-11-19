"""Plain parts shared by the WhisperX GPU runners (#297, #314).

``llm.gpu.colab_diarize`` (the documented path: the owner's Colab) and ``llm.gpu.modal_diarize`` (built first, kept)
both use these: the batch cap, the output file name, the usage row, finding the media file behind a meeting page, and
fetching it. Nothing here needs a GPU, Modal, Colab or the network at import time.
"""

from __future__ import annotations

import html as html_lib
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin, urlsplit

STEP_NAME = "whisperx_diarization"
DEFAULT_LIMIT = 3
DEFAULT_MODEL_SIZE = "small"        # fits a T4's 16 GB
MEETING_LANGUAGE = "en"             # US local meetings; a guess from a silent opening can pick a language with no aligner
FETCH_TIMEOUT_SECONDS = 3600        # one long meeting; a hung stream stops here
# whisperx 3.8 needs numpy>=2.1 and ctranslate2>=4.5. A numpy<2 pin made pip fall back to ctranslate2 4.4.0, which
# Debian trixie (Modal's base) refuses to load ("cannot enable executable stack"); whisperx pins torch itself.
WHISPERX_PACKAGES = ["whisperx>=3.8,<4", "ctranslate2>=4.6,<5", "requests"]
# Some city archives answer python-requests with an error page; a plain browser identity gets the real one.
FETCH_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}


def plan_batch(items: list[str], limit: int = DEFAULT_LIMIT) -> list[str]:
    """Items to run: trimmed, empty and repeated ones dropped, at most ``limit`` (at least one)."""
    out: list[str] = []
    for item in items:
        item = (item or "").strip()
        if item and item not in out:
            out.append(item)
    return out[: max(1, int(limit))]


def is_url(item: str) -> bool:
    return bool(re.match(r"^https?://", item or ""))


def output_name(item: str) -> str:
    """A file-safe output name for an item."""
    base = re.sub(r"^https?://[^/]+/", "", item).split("?")[0]
    base = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", base)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") + ".diarized.json"


def base_usage_row(platform: str, item: str, gpu: str, started_ts: str, seconds: float, status_code: str,
                   estimated_cost_usd: float | None) -> dict:
    """One usage row per item, in the shape of ``llm.usage`` GPU rows, marked as an estimate."""
    return {
        "platform_name": platform,
        "step_name": STEP_NAME,
        "item_name": item,
        "gpu_name": gpu.upper(),
        "started_ts": started_ts,
        "duration_seconds": round(float(seconds), 3),
        "gpu_hours": float(seconds) / 3600.0,
        "estimated_cost_usd": estimated_cost_usd,
        "is_estimated": True,
        "run_status_code": status_code,
    }


def exit_code(rows: list[dict]) -> int:
    """1 when a batch ran items and none succeeded, so the run shows failed instead of green."""
    return 1 if rows and not any(r.get("run_status_code") == "ok" for r in rows) else 0


MEDIA_EXTENSIONS = (".mp4", ".mp3", ".m4a", ".opus", ".wav", ".webm", ".ogg", ".m3u8")
_ANCHOR = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_PLAYER_SRC = re.compile(r"<(?:video|audio|source|iframe|embed)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)", re.IGNORECASE)
_OG_VIDEO = re.compile(r"<meta\b[^>]*?property\s*=\s*[\"']og:video(?::secure_url|:url)?[\"'][^>]*?"
                       r"content\s*=\s*[\"']([^\"']+)", re.IGNORECASE)
_QUOTED_URL = re.compile(r"[\"'](https?:(?:\\?/){2}[^\"'\s<>]+)[\"']")


def _is_media(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(MEDIA_EXTENSIONS)


def media_link_from_html(html: str, page_url: str) -> str | None:
    """The meeting page's media file: a labelled or direct link, the embedded player's source, its og:video, or a
    media URL inside a script (HLS ``.m3u8`` included); None if there is none.

    Archives such as CCTV hide a short-lived signed file link behind "Download", which is hard to copy on a phone.
    """
    def full(u: str) -> str:
        return urljoin(page_url, html_lib.unescape(u.strip()).replace("\\/", "/"))

    for href, text in _ANCHOR.findall(html):
        url, label = full(href), re.sub(r"<[^>]+>", " ", text)
        if _is_media(url) or (re.search(r"download", label, re.IGNORECASE)
                              and re.search(r"mp4|mp3|audio|video", label, re.IGNORECASE)):
            return url
    for found in (_PLAYER_SRC.findall(html), _OG_VIDEO.findall(html), _QUOTED_URL.findall(html)):
        for u in found:
            if _is_media(full(u)):
                return full(u)
    return None


def player_sources(html: str, page_url: str) -> list[str]:
    """Up to 5 iframe, embed and player sources on a page, so a page with no media link says where to look next."""
    return [urljoin(page_url, html_lib.unescape(u)) for u in _PLAYER_SRC.findall(html)][:5]


def fetch_media(url: str, dest_dir: Path) -> Path:
    """Download a direct media URL, or the media behind a meeting page, into ``dest_dir``; returns the file.

    A page (``text/html``) is searched for its media link; an HLS ``.m3u8`` stream is pulled to 16 kHz mono WAV with
    ffmpeg. Needs the network and ``requests`` (and ffmpeg for streams), so it is called only inside a run.
    """
    import requests

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / "audio"
    where = url
    head = requests.get(where, stream=True, timeout=120, headers=FETCH_HEADERS)
    head.raise_for_status()
    if head.headers.get("content-type", "").startswith("text/html"):
        link = media_link_from_html(head.text, head.url)
        if not link:
            raise ValueError(f"no audio or video link on that page; players: {player_sources(head.text, head.url)}")
        where = link
    head.close()
    if urlsplit(where).path.lower().endswith(".m3u8"):   # a stream: ffmpeg pulls just the audio
        tmp = tmp.with_suffix(".wav")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-user_agent", FETCH_HEADERS["User-Agent"], "-i", where,
                        "-vn", "-ac", "1", "-ar", "16000", str(tmp)], check=True, timeout=FETCH_TIMEOUT_SECONDS)
        return tmp
    with requests.get(where, stream=True, timeout=120, headers=FETCH_HEADERS) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return tmp
