"""
Build ``YouTubeTranscriptApi`` with optional HTTP/SOCKS proxy (VPN local proxy port).

Set ``YOUTUBE_TRANSCRIPT_PROXY`` to your VPN's local proxy, e.g.::

    export YOUTUBE_TRANSCRIPT_PROXY=socks5://127.0.0.1:1080

Rotating VPNs: use the proxy port the VPN app exposes; system-wide rotation alone
may not apply to WSL/Python unless traffic goes through that proxy.
"""

from __future__ import annotations

import os
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig


def resolve_transcript_proxy_url(explicit: Optional[str] = None) -> Optional[str]:
    url = (explicit or os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip()
    return url or None


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


def build_youtube_transcript_api(proxy_url: Optional[str] = None) -> YouTubeTranscriptApi:
    """``YouTubeTranscriptApi`` using ``YOUTUBE_TRANSCRIPT_PROXY`` when set."""
    url = resolve_transcript_proxy_url(proxy_url)
    if not url:
        return YouTubeTranscriptApi()
    return YouTubeTranscriptApi(
        proxy_config=GenericProxyConfig(http_url=url, https_url=url),
    )
