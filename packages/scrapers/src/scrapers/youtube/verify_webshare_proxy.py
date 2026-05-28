#!/usr/bin/env python3
"""Quick Webshare credential check (fixes HTTP 407 Proxy Authentication Required)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv
from loguru import logger

load_dotenv(_REPO / ".env")

from scrapers.youtube.transcript_api_client import (  # noqa: E402
    resolve_webshare_filter_ip_locations,
    resolve_webshare_proxy_credentials,
    verify_webshare_proxy_connectivity,
)


def main() -> int:
    user, _ = resolve_webshare_proxy_credentials()
    if not user:
        logger.error(
            "Set PROXY_USER_NAME and PROXY_PASSWORD in .env "
            "(from https://dashboard.webshare.io/proxy/settings)"
        )
        return 2
    locs = resolve_webshare_filter_ip_locations()
    if locs:
        logger.info("WEBSHARE_FILTER_IP_LOCATIONS={}", ",".join(locs))
    ok, msg = verify_webshare_proxy_connectivity()
    if ok:
        logger.info("{}", msg)
        return 0
    logger.error("{}", msg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
