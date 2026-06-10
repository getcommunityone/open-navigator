#!/usr/bin/env python3
"""
YouTube discovery only — no DB writes. Use to debug website crawl / Civic / enrich.

  .venv/bin/python scripts/datasources/jurisdiction_pilot/debug_youtube_discovery.py \\
    --website https://www.augustaga.gov \\
    --name "Augusta-Richmond County" \\
    --state GA \\
    --cookies youtube_cookies.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.datasources.jurisdiction_pilot.google_civic_youtube import (  # noqa: E402
    get_youtube_from_civic_api,
)
from scripts.datasources.jurisdiction_pilot.website_youtube_search import (  # noqa: E402
    crawl_website_for_youtube,
    search_duckduckgo_for_youtube,
    search_multiple_queries,
)
from scrapers.youtube.youtube_channel_enrich import (  # noqa: E402
    enrich_channel,
)
from scrapers.youtube.pattern_match_gate import (  # noqa: E402
    passes_pattern_match_gate,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--website", required=True, help="Jurisdiction homepage URL")
    p.add_argument("--name", required=True, help="Jurisdiction display name (Civic API)")
    p.add_argument("--state", required=True, help="USPS state code")
    p.add_argument("--cookies", default="youtube_cookies.txt")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for name in (
        "scripts.datasources.jurisdiction_pilot.website_youtube_search",
        "scrapers.youtube.youtube_channel_enrich",
        "scripts.datasources.jurisdiction_pilot.google_civic_youtube",
    ):
        logging.getLogger(name).setLevel(logging.DEBUG)

    sess = requests.Session()
    sess.verify = False
    cookies = args.cookies if Path(args.cookies).is_file() else None

    print(f"\n=== website: {args.website}")
    print(f"=== name: {args.name} ({args.state})\n")

    civic = get_youtube_from_civic_api(args.name, args.state)
    print(f"[civic_api] {len(civic)} url(s)")
    for u in civic:
        print(f"  {u}")

    ddg = search_duckduckgo_for_youtube(args.website, session=sess)
    print(f"\n[duckduckgo site:search] {len(ddg)} url(s)")
    for u in ddg:
        print(f"  {u}")

    crawl = crawl_website_for_youtube(args.website, session=sess)
    print(f"\n[crawl paths] {len(crawl)} url(s)")
    for u in crawl:
        print(f"  {u}")

    merged = search_multiple_queries(args.website, session=sess)
    print(f"\n[search_multiple_queries] {len(merged)} url(s)")
    for u in merged:
        print(f"  {u}")

    if not merged:
        print("\n(no channels — pilot would try pattern_match next)")
        return 0

    print("\n=== enrich each candidate ===")
    for url in merged:
        ch = {"channel_url": url, "discovery_method": "website_search"}
        enriched = enrich_channel(
            channel=ch,
            jurisdiction_name=args.name,
            jurisdiction_state_code=args.state,
            jurisdiction_homepage=args.website,
            session=sess,
            cookies_file=cookies,
        )
        gate_ok = passes_pattern_match_gate(
            channel_title=str(enriched.get("channel_title") or ""),
            channel_description=str(enriched.get("channel_description") or ""),
            jurisdiction_name=args.name,
            jurisdiction_state_code=args.state,
            jurisdiction_homepage=args.website,
            external_links=enriched.get("external_links"),
            backlinks_to_jurisdiction=enriched.get("back_links_to_jurisdiction_website"),
        )
        print(f"\n--- {url}")
        print(
            json.dumps(
                {
                    "channel_id": enriched.get("channel_id"),
                    "channel_title": enriched.get("channel_title"),
                    "official_meeting_confidence": enriched.get("official_meeting_confidence"),
                    "back_links_to_jurisdiction_website": enriched.get(
                        "back_links_to_jurisdiction_website"
                    ),
                    "pattern_match_gate_pass": gate_ok,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
