"""
Build ``YouTubeTranscriptApi`` with optional HTTP/SOCKS proxy (VPN local proxy port).

Set ``YOUTUBE_TRANSCRIPT_PROXY`` to your VPN's local proxy, e.g.::

    export YOUTUBE_TRANSCRIPT_PROXY=socks5://127.0.0.1:1080

Rotating VPNs: use the proxy port the VPN app exposes; system-wide rotation alone
may not apply to WSL/Python unless traffic goes through that proxy.
"""

from __future__ import annotations

import os
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig


def resolve_transcript_proxy_url(explicit: Optional[str] = None) -> Optional[str]:
    url = (explicit or os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip()
    return url or None


def build_youtube_transcript_api(proxy_url: Optional[str] = None) -> YouTubeTranscriptApi:
    """``YouTubeTranscriptApi`` using ``YOUTUBE_TRANSCRIPT_PROXY`` when set."""
    url = resolve_transcript_proxy_url(proxy_url)
    if not url:
        return YouTubeTranscriptApi()
    return YouTubeTranscriptApi(
        proxy_config=GenericProxyConfig(http_url=url, https_url=url),
    )
