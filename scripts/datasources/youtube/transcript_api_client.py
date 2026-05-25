"""
Build ``YouTubeTranscriptApi`` ([jdepoix/youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api))
with optional proxy and Netscape ``cookies.txt``.

Preferred over yt-dlp for captions: no video download, lighter on IP blocks when
combined with ``--cookies``, Webshare residential proxies (``PROXY_USER_NAME`` /
``PROXY_PASSWORD``), or ``YOUTUBE_TRANSCRIPT_PROXY``.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple
from urllib.parse import urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

# Descending priority per library docs.
DEFAULT_TRANSCRIPT_LANGUAGES: tuple[str, ...] = ("en", "en-US", "en-GB", "de", "es")


def format_transcript_error(exc: BaseException, *, max_len: int = 800) -> str:
    """Full exception chain for logs (avoids truncating ``Caused by ProxyError…``)."""
    parts: list[str] = []
    seen: set[int] = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        line = f"{type(cur).__name__}: {cur}".strip()
        if line and (not parts or parts[-1] != line):
            parts.append(line)
        nxt = cur.__cause__
        if nxt is None and cur.__context__ is not cur.__cause__:
            nxt = cur.__context__
        cur = nxt
    if not parts:
        return type(exc).__name__
    text = " → ".join(parts)
    if len(text) <= max_len:
        return text
    if len(parts) == 1:
        return text[: max_len - 3] + "..."
    tail = parts[-1]
    head = " → ".join(parts[:-1])
    budget = max_len - len(tail) - 5
    if budget > 40:
        return head[:budget] + " → " + tail
    return tail[:max_len]


def transcript_failure_hint(message: str) -> Optional[str]:
    """Short actionable hint from a formatted transcript error string."""
    lower = (message or "").lower()
    if "407" in lower or "proxy authentication required" in lower:
        return (
            "Webshare proxy auth failed (HTTP 407). In .env set PROXY_USER_NAME and "
            "PROXY_PASSWORD from https://dashboard.webshare.io/proxy/settings (Proxy Username / "
            "Proxy Password) — not the per-IP password in the proxy list. Quote passwords with "
            "special chars: PROXY_PASSWORD='your-password'. Test: "
            ".venv/bin/python scripts/datasources/youtube/verify_webshare_proxy.py"
        )
    if "proxyerror" in lower or (
        "max retries exceeded" in lower and "proxy" in lower
    ):
        return (
            "Caption proxy could not reach YouTube. Check PROXY_USER_NAME / PROXY_PASSWORD "
            "(Webshare dashboard proxy settings), try WEBSHARE_FILTER_IP_LOCATIONS=us, "
            "or run: .venv/bin/python scripts/datasources/youtube/verify_webshare_proxy.py"
        )
    if "not a bot" in lower or "sign in to confirm" in lower:
        return (
            "YouTube bot check — re-export youtube_cookies.txt while logged in, "
            "use --cookies, and keep yt-dlp on direct egress (do not set YOUTUBE_YTDLP_USE_WEBSHARE=1)."
        )
    if "429" in lower or "too many requests" in lower or "too many 429" in lower:
        if "timedtext" in lower or "/api/timedtext" in lower:
            return (
                "YouTube rate-limited the signed caption download (/api/timedtext) — proxy auth "
                "is OK but this IP hit too many caption fetches. Use WORKERS=1, "
                "TRANSCRIPT_DELAY=25+, fresh youtube_cookies.txt, "
                "WEBSHARE_FILTER_IP_LOCATIONS=us, optional WEBSHARE_RETRIES_WHEN_BLOCKED=15; "
                "pause 30–60 min or SKIP_TRANSCRIPTS=1 and backfill in small batches."
            )
        return (
            "Rate limited (HTTP 429) — increase --transcript-delay, use --workers 1, "
            "wait 30–60 min, then retry."
        )
    if "transcriptsdisabled" in lower or "captions disabled" in lower:
        return "Uploader disabled captions; nothing to fetch for this video."
    if "no transcript" in lower or "notranscriptfound" in lower:
        return "No caption track in any requested language (en, en-US, …)."
    if "video unavailable" in lower or "videounavailable" in lower:
        return "Video private, deleted, or region-blocked."
    if "no subtitles" in lower or "subtitle" in lower and "metadata" in lower:
        return "yt-dlp saw the video but found no downloadable subtitle track."
    return None


def resolve_transcript_proxy_url(explicit: Optional[str] = None) -> Optional[str]:
    url = (explicit or os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip()
    return url or None


def resolve_webshare_proxy_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Webshare residential proxy credentials from the environment.

    Reads ``PROXY_USER_NAME`` and ``PROXY_PASSWORD`` (also accepts
    ``WEBSHARE_PROXY_USERNAME`` / ``WEBSHARE_PROXY_PASSWORD``).
    """
    user = (
        (os.getenv("PROXY_USER_NAME") or "").strip()
        or (os.getenv("WEBSHARE_PROXY_USERNAME") or "").strip()
    )
    password = (
        (os.getenv("PROXY_PASSWORD") or "").strip()
        or (os.getenv("WEBSHARE_PROXY_PASSWORD") or "").strip()
    )
    if user and password:
        return user, password
    return None, None


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def resolve_webshare_filter_ip_locations() -> Optional[list[str]]:
    """
    Country codes for Webshare rotating pool (e.g. ``de``, ``us``).

    Set ``WEBSHARE_FILTER_IP_LOCATIONS`` or ``PROXY_FILTER_IP_LOCATIONS`` to a
    comma-separated list (``de,us``). Matches ``WebshareProxyConfig.filter_ip_locations``.
    """
    raw = (
        (os.getenv("WEBSHARE_FILTER_IP_LOCATIONS") or "").strip()
        or (os.getenv("PROXY_FILTER_IP_LOCATIONS") or "").strip()
    )
    if not raw:
        return None
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
    return codes or None


def resolve_webshare_retries_when_blocked() -> int:
    """``WebshareProxyConfig.retries_when_blocked`` (default 10 per upstream library)."""
    raw = (os.getenv("WEBSHARE_RETRIES_WHEN_BLOCKED") or "").strip()
    if not raw:
        return 10
    try:
        return max(0, int(raw))
    except ValueError:
        return 10


def verify_webshare_proxy_connectivity(
    *,
    timeout_sec: float = 20.0,
) -> tuple[bool, str]:
    """
    Return ``(ok, message)`` after a minimal HTTPS request through Webshare.

    Use this when logs show ``407 Proxy Authentication Required``.
    """
    proxy_user, proxy_password = resolve_webshare_proxy_credentials()
    if not proxy_user or not proxy_password:
        return False, "PROXY_USER_NAME / PROXY_PASSWORD not set in environment"
    cfg = _webshare_proxy_config(proxy_user, proxy_password)
    proxies = cfg.to_requests_dict()
    try:
        import requests

        r = requests.get(
            "https://www.youtube.com/robots.txt",
            proxies=proxies,
            timeout=timeout_sec,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        if r.status_code >= 500:
            return False, f"Webshare tunnel OK but YouTube returned HTTP {r.status_code}"
        return True, (
            f"Webshare auth OK (HTTP {r.status_code} via p.webshare.io, "
            f"user={proxy_user!r}, rotate suffix applied by library)"
        )
    except Exception as exc:
        msg = format_transcript_error(exc, max_len=500)
        if "407" in msg.lower():
            return False, (
                "Webshare rejected credentials (407 Proxy Authentication Required). "
                "Copy Proxy Username and Proxy Password from "
                "https://dashboard.webshare.io/proxy/settings into .env — "
                "not the password shown on each IP row in the proxy list."
            )
        return False, f"Webshare connectivity failed: {msg}"


def _webshare_proxy_config(
    proxy_username: str,
    proxy_password: str,
) -> WebshareProxyConfig:
    locations = resolve_webshare_filter_ip_locations()
    kwargs: dict[str, Any] = {
        "proxy_username": proxy_username,
        "proxy_password": proxy_password,
        "retries_when_blocked": resolve_webshare_retries_when_blocked(),
    }
    if locations:
        kwargs["filter_ip_locations"] = locations
    return WebshareProxyConfig(**kwargs)


def resolve_ytdlp_proxy_url(explicit: Optional[str] = None) -> Optional[str]:
    """
    Proxy URL for yt-dlp (video catalog / subtitle fallback).

    Order: explicit / ``--proxy`` → ``YOUTUBE_HTTPS_PROXY`` → ``YOUTUBE_TRANSCRIPT_PROXY``.
    Webshare (``PROXY_USER_NAME`` / ``PROXY_PASSWORD``) is **not** used for yt-dlp unless
    ``YOUTUBE_YTDLP_USE_WEBSHARE=1`` — it is for ``youtube-transcript-api`` via
    ``build_proxy_config()`` and often breaks yt-dlp HTTPS to ``www.youtube.com``.
    """
    url = (
        (explicit or "").strip()
        or (os.getenv("YOUTUBE_HTTPS_PROXY") or "").strip()
        or (os.getenv("YOUTUBE_HTTP_PROXY") or "").strip()
        or (os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip()
    )
    if url:
        return url
    if _env_truthy("YOUTUBE_YTDLP_USE_WEBSHARE"):
        proxy_user, proxy_password = resolve_webshare_proxy_credentials()
        if proxy_user and proxy_password:
            return _webshare_proxy_config(proxy_user, proxy_password).http_url
    return None


def build_proxy_config(
    proxy_url: Optional[str] = None,
) -> Optional[GenericProxyConfig | WebshareProxyConfig]:
    """
    Prefer Webshare when credentials are set; else generic HTTP/SOCKS URL.

    Webshare uses rotating residential IPs (``-rotate`` in proxy URL). Optional
    ``WEBSHARE_FILTER_IP_LOCATIONS=de,us`` limits the rotation pool to those countries.
    """
    proxy_user, proxy_password = resolve_webshare_proxy_credentials()
    if proxy_user and proxy_password:
        return _webshare_proxy_config(proxy_user, proxy_password)
    url = resolve_transcript_proxy_url(proxy_url)
    if url:
        return GenericProxyConfig(http_url=url, https_url=url)
    return None


def resolve_cookies_path(explicit: Optional[str] = None) -> Optional[str]:
    path = (
        (explicit or "").strip()
        or (os.getenv("YOUTUBE_COOKIES") or "").strip()
        or (os.getenv("YOUTUBE_COOKIES_FILE") or "").strip()
        or "youtube_cookies.txt"
    )
    p = Path(path)
    return str(p) if p.is_file() else None


def check_proxy_reachable(
    proxy_url: str,
    *,
    timeout_sec: float = 3.0,
) -> Tuple[bool, str]:
    """Return (ok, message). Fails fast when SOCKS/HTTP proxy port is not listening."""
    parsed = urlparse(proxy_url.strip())
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if not port:
        scheme = (parsed.scheme or "").lower()
        port = 1080 if scheme.startswith("socks") else 8080
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True, f"{host}:{port} accepts connections"
    except OSError as exc:
        return False, f"cannot connect to {host}:{port} ({exc})"


def _requests_session_with_cookies(cookies_file: Optional[str]) -> Optional[Any]:
    """``requests.Session`` with YouTube cookies from Netscape export."""
    path = (cookies_file or "").strip()
    if not path or not Path(path).is_file():
        return None
    try:
        import requests
        from http.cookiejar import MozillaCookieJar

        jar = MozillaCookieJar(path)
        jar.load(ignore_discard=True, ignore_expires=True)
        session = requests.Session()
        session.cookies = jar
        session.headers.update(
            {
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )
        return session
    except Exception:
        return None


def build_youtube_transcript_api(
    proxy_url: Optional[str] = None,
    *,
    cookies_path: Optional[str] = None,
) -> YouTubeTranscriptApi:
    """
    ``YouTubeTranscriptApi`` with Webshare, generic proxy URL, and optional cookies.

    When ``PROXY_USER_NAME`` and ``PROXY_PASSWORD`` are set, all requests use
    ``WebshareProxyConfig`` (rotating residential; new IP per request). Set
    ``WEBSHARE_FILTER_IP_LOCATIONS=de,us`` to limit the pool. Otherwise falls back to
    ``YOUTUBE_TRANSCRIPT_PROXY`` / ``GenericProxyConfig``.

    Pass ``cookies_path`` (Netscape ``cookies.txt``) to further reduce blocks.
    """
    proxy_config = build_proxy_config(proxy_url)
    http_client = _requests_session_with_cookies(cookies_path)
    if proxy_config is not None:
        return YouTubeTranscriptApi(
            proxy_config=proxy_config,
            http_client=http_client,
        )
    if http_client is not None:
        return YouTubeTranscriptApi(http_client=http_client)
    return YouTubeTranscriptApi()


def _fetched_meta(fetched: Any, *, fallback_language: str = "en") -> tuple[str, bool]:
    language = (
        getattr(fetched, "language_code", None)
        or getattr(fetched, "language", None)
        or fallback_language
        or "en"
    )
    return str(language), bool(getattr(fetched, "is_generated", True))


def _fetched_to_payload(
    video_id: str,
    fetched: Any,
    *,
    language: str,
    is_auto: bool,
) -> dict[str, Any]:
    snippets = list(fetched.snippets)
    segments = [
        {
            "text": snippet.text,
            "start": snippet.start,
            "duration": snippet.duration,
        }
        for snippet in snippets
    ]
    raw_text = " ".join(s["text"] for s in segments if s.get("text"))
    return {
        "video_id": video_id,
        "raw_text": raw_text,
        "segments": segments,
        "language": language,
        "is_auto_generated": is_auto,
        "transcript_source": "youtube_transcript_api",
    }


def _fetch_object_with_language_priority(
    api: YouTubeTranscriptApi,
    video_id: str,
    languages: Sequence[str],
    *,
    preserve_formatting: bool = True,
) -> Any:
    """Return ``FetchedTranscript`` via ``fetch`` / ``list().find_transcript``."""
    langs = list(languages) or list(DEFAULT_TRANSCRIPT_LANGUAGES)
    try:
        return api.fetch(
            video_id,
            languages=langs,
            preserve_formatting=preserve_formatting,
        )
    except NoTranscriptFound:
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(langs)
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(langs)
            except NoTranscriptFound:
                available = list(transcript_list)
                if not available:
                    raise
                transcript = available[0]
        return transcript.fetch(preserve_formatting=preserve_formatting)


def fetch_transcript_bundle(
    video_id: str,
    *,
    proxy_url: Optional[str] = None,
    cookies_file: Optional[str] = None,
    languages: Optional[Iterable[str]] = None,
    retry_on_block: bool = True,
) -> dict[str, Any]:
    """
    Single ``fetch(..., preserve_formatting=True)`` for bronze + policy cache.

    ``caption_raw_data`` is ``FetchedTranscript.to_raw_data()`` (may include HTML markup).
    """
    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id required")

    langs = tuple(languages) if languages is not None else DEFAULT_TRANSCRIPT_LANGUAGES
    cookies_resolved = resolve_cookies_path(cookies_file)

    def _attempt() -> dict[str, Any]:
        api = build_youtube_transcript_api(proxy_url, cookies_path=cookies_resolved)
        fetched = _fetch_object_with_language_priority(
            api, vid, langs, preserve_formatting=True
        )
        language, is_auto = _fetched_meta(fetched)
        payload = _fetched_to_payload(vid, fetched, language=language, is_auto=is_auto)
        payload["caption_raw_data"] = fetched.to_raw_data()
        payload["caption_preserve_formatting"] = True
        return payload

    try:
        return _attempt()
    except RequestBlocked:
        if not retry_on_block:
            raise
        ws_user, ws_pass = resolve_webshare_proxy_credentials()
        if (
            not cookies_resolved
            and not resolve_transcript_proxy_url(proxy_url)
            and not (ws_user and ws_pass)
        ):
            raise
        return _attempt()


def _fetch_with_language_priority(
    api: YouTubeTranscriptApi,
    video_id: str,
    languages: Sequence[str],
) -> dict[str, Any]:
    """Use ``fetch`` / ``list().find_transcript`` per upstream README."""
    fetched = _fetch_object_with_language_priority(
        api, video_id, languages, preserve_formatting=True
    )
    language, is_auto = _fetched_meta(fetched)
    return _fetched_to_payload(video_id, fetched, language=language, is_auto=is_auto)


def fetch_transcript_from_api(
    video_id: str,
    *,
    proxy_url: Optional[str] = None,
    cookies_file: Optional[str] = None,
    languages: Optional[Iterable[str]] = None,
    retry_on_block: bool = True,
) -> dict[str, Any]:
    """
    Fetch captions via youtube-transcript-api only (no yt-dlp).

    Raises ``TranscriptsDisabled``, ``VideoUnavailable``, ``IpBlocked``, ``NoTranscriptFound``,
    and other API errors for the caller to handle.
    """
    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id required")

    langs = tuple(languages) if languages is not None else DEFAULT_TRANSCRIPT_LANGUAGES
    cookies_resolved = resolve_cookies_path(cookies_file)

    return fetch_transcript_bundle(
        vid,
        proxy_url=proxy_url,
        cookies_file=cookies_resolved,
        languages=langs,
        retry_on_block=retry_on_block,
    )


def describe_caption_egress(
    *,
    explicit_proxy_url: Optional[str] = None,
    cookies_path: Optional[str] = None,
    ytdlp_fallback: bool = True,
) -> dict[str, Any]:
    """
    Human-readable caption routing for logs (caption API vs yt-dlp egress).

    Webshare (``PROXY_USER_NAME`` / ``PROXY_PASSWORD``) is used by the caption API even when
    ``YOUTUBE_TRANSCRIPT_PROXY`` is unset.
    """
    ws_user, _ws_pass = resolve_webshare_proxy_credentials()
    ws_locations = resolve_webshare_filter_ip_locations()
    generic = resolve_transcript_proxy_url(explicit_proxy_url)

    if ws_user:
        caption_mode = "webshare"
        loc = f", pool={','.join(ws_locations)}" if ws_locations else ""
        caption_detail = f"Webshare residential (user={ws_user!r}{loc})"
    elif generic:
        caption_mode = "generic_proxy"
        caption_detail = f"YOUTUBE_TRANSCRIPT_PROXY / --proxy ({generic})"
    else:
        caption_mode = "direct"
        caption_detail = "direct egress (WSL/host network; no Webshare or YOUTUBE_TRANSCRIPT_PROXY)"

    ytdlp_url = resolve_ytdlp_proxy_url(explicit_proxy_url)
    if ytdlp_url:
        ytdlp_mode = "webshare" if "webshare.io" in ytdlp_url else "generic_proxy"
        ytdlp_detail = ytdlp_url.split("@")[-1][:80]
    else:
        ytdlp_mode = "direct"
        ytdlp_detail = "direct + cookies (default)"

    return {
        "caption_api": "youtube-transcript-api (transcript_api_client)",
        "caption_egress_mode": caption_mode,
        "caption_egress_detail": caption_detail,
        "webshare_configured": bool(ws_user),
        "webshare_user": ws_user,
        "webshare_locations": ws_locations,
        "explicit_proxy": generic,
        "cookies_path": cookies_path,
        "ytdlp_fallback": ytdlp_fallback,
        "ytdlp_egress_mode": ytdlp_mode,
        "ytdlp_egress_detail": ytdlp_detail,
    }


def summarize_transcript_payload(payload: Optional[dict[str, Any]]) -> str:
    """One-line fetch outcome for logs."""
    if not payload:
        return "no payload"
    src = str(payload.get("transcript_source") or "?")
    lang = str(payload.get("language") or "?")
    auto = "auto" if payload.get("is_auto_generated") else "manual"
    chars = len(str(payload.get("raw_text") or ""))
    segs = len(payload.get("segments") or [])
    return f"source={src} lang={lang} {auto} chars={chars} segments={segs}"


def log_caption_fetch_setup(
    logger: Any,
    *,
    cookies_path: Optional[str],
    explicit_proxy_url: Optional[str] = None,
    ytdlp_fallback: bool = True,
    verify_webshare: bool = False,
) -> None:
    """Log caption API path, egress, cookies, and optional Webshare connectivity check."""
    info = describe_caption_egress(
        explicit_proxy_url=explicit_proxy_url,
        cookies_path=cookies_path,
        ytdlp_fallback=ytdlp_fallback,
    )
    logger.info("Caption API: {}", info["caption_api"])
    logger.info("Caption egress: {}", info["caption_egress_detail"])
    if info["cookies_path"]:
        logger.info("Cookies: {}", info["cookies_path"])
    else:
        logger.warning(
            "Cookies: (none) — export youtube_cookies.txt while logged into YouTube"
        )
    if info["ytdlp_fallback"]:
        logger.info("yt-dlp fallback: enabled ({})", info["ytdlp_egress_detail"])
    else:
        logger.info("yt-dlp fallback: disabled (caption API only)")
    if info["webshare_configured"] and info["explicit_proxy"]:
        logger.info(
            "Note: Webshare env wins for caption API; YOUTUBE_TRANSCRIPT_PROXY is for yt-dlp / generic only"
        )
    if verify_webshare and info["webshare_configured"]:
        ok, msg = verify_webshare_proxy_connectivity()
        if ok:
            logger.info("Webshare check: {}", msg)
        else:
            logger.error("Webshare check failed: {}", msg)


__all__ = [
    "DEFAULT_TRANSCRIPT_LANGUAGES",
    "format_transcript_error",
    "transcript_failure_hint",
    "build_proxy_config",
    "build_youtube_transcript_api",
    "check_proxy_reachable",
    "fetch_transcript_bundle",
    "fetch_transcript_from_api",
    "resolve_cookies_path",
    "resolve_transcript_proxy_url",
    "resolve_webshare_filter_ip_locations",
    "resolve_webshare_proxy_credentials",
    "resolve_webshare_retries_when_blocked",
    "resolve_ytdlp_proxy_url",
    "verify_webshare_proxy_connectivity",
    "describe_caption_egress",
    "summarize_transcript_payload",
    "log_caption_fetch_setup",
]
