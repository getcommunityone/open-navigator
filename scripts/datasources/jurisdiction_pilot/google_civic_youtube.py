"""
Get verified YouTube handles from Google Civic Information API.

The Google Civic Information API returns official government offices with their
verified social media channels, including YouTube handles linked directly to
those municipal seats or county offices. This is much more reliable than
pattern matching or API searches.

Requires a free API key from:
https://console.cloud.google.com/
(project > APIs & Services > Enable "Civic Information API")
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_CIVIC_API = "https://www.googleapis.com/civicinfo/v2/representatives"
_TIMEOUT_S = 10

# Environment variable for API key
_API_KEY = os.getenv("GOOGLE_CIVIC_API_KEY")


def _normalize_youtube_url(handle_or_url: str) -> str | None:
    """Normalize YouTube handle or URL to standard form."""
    if not handle_or_url:
        return None

    s = handle_or_url.strip()

    # If it's already a full URL, extract and normalize
    if s.startswith("http"):
        parsed = urlparse(s)
        if "youtube.com" in parsed.netloc.lower():
            # Extract the path component (@handle, c/name, channel/id, user/name)
            parts = parsed.path.lstrip("/").split("/")
            if parts and parts[0]:
                return f"https://www.youtube.com/{parts[0]}"
        return None

    # If it's just a handle (starts with @) or plain identifier
    if s.startswith("@"):
        return f"https://www.youtube.com/{s}"
    elif s and not s.startswith("/"):
        # Could be @handle without the @, or channel-like identifier
        if not any(c in s for c in (".", "/")):
            return f"https://www.youtube.com/@{s}"

    return None


def get_youtube_from_civic_api(
    address: str,
    state_code: str,
) -> list[str]:
    """
    Query Google Civic Information API for YouTube handles of government officials
    at the given address/jurisdiction.

    Returns list of verified YouTube channel URLs.
    """
    if not _API_KEY:
        logger.debug("GOOGLE_CIVIC_API_KEY not set; skipping Civic API lookup")
        return []

    if not address:
        return []

    # Format address as "address state" for the Civic API
    query_address = f"{address} {state_code}"

    params = {
        "address": query_address,
        "key": _API_KEY,
        "levels": "city,county",  # Focus on municipal and county officials
    }

    youtube_urls = []
    seen: set[str] = set()

    try:
        logger.debug("Querying Civic API for %s", query_address)
        resp = requests.get(_CIVIC_API, params=params, timeout=_TIMEOUT_S)

        if resp.status_code == 200:
            data = resp.json()

            # Extract YouTube URLs from officials' channels
            officials = data.get("officials", [])
            for official in officials:
                channels = official.get("channels", [])
                for channel in channels:
                    # Channel format: {"type": "YouTube", "id": "@Handle"} or full URL
                    if channel.get("type") == "YouTube":
                        channel_id = channel.get("id", "")
                        normalized = _normalize_youtube_url(channel_id)
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            youtube_urls.append(normalized)
                            logger.debug("  → found official: %s", normalized)

            if youtube_urls:
                logger.debug("Found %d verified YouTube URLs from Civic API", len(youtube_urls))
        else:
            logger.debug("Civic API returned %d for %s", resp.status_code, query_address)

    except requests.RequestException as exc:
        logger.debug("Civic API lookup failed for %s: %s", query_address, exc)
    except (KeyError, ValueError, TypeError) as exc:
        logger.debug("Error parsing Civic API response: %s", exc)

    return youtube_urls
