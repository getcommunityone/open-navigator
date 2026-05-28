#!/usr/bin/env python3
"""Smoke test for Cobb County website YouTube discovery behavior."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

COBB_HOMEPAGE = "https://www.cobbcounty.org/"
EXPECTED_URL = "https://www.youtube.com/user/CobbCountyGovt"


async def run() -> int:
    async with YouTubeChannelDiscovery() as discovery:
        channels = await discovery._scrape_website_for_channels(COBB_HOMEPAGE)
        found_expected = EXPECTED_URL in channels

        resolved = None
        if found_expected:
            resolved = await discovery._check_channel_exists(EXPECTED_URL, "website_scrape")

        print(
            json.dumps(
                {
                    "homepage": COBB_HOMEPAGE,
                    "expected_url": EXPECTED_URL,
                    "found_expected": found_expected,
                    "channels_found": channels,
                    "resolved_channel_id": (resolved or {}).get("channel_id", ""),
                },
                indent=2,
            )
        )

        if not found_expected:
            return 1
        if not resolved or not resolved.get("channel_id"):
            return 2
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
