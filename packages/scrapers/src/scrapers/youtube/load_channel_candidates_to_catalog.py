#!/usr/bin/env python3
"""Load discovered channel candidates CSV into bronze YouTube catalog per jurisdiction.

Expected CSV columns:
- jurisdiction_id
- county_name (or jurisdiction_name)
- channel_id
- channel_url (optional)
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="Path to candidates CSV")
    p.add_argument("--state", default="GA", help="State code for load_youtube_for_jurisdiction")
    p.add_argument("--jurisdiction-type", default="county")
    p.add_argument("--max-videos", type=int, default=100)
    p.add_argument(
        "--min-duration-seconds",
        type=int,
        default=120,
        help="Skip videos shorter than this many seconds (default: 120)",
    )
    p.add_argument("--python", default=".venv/bin/python", help="Python executable")
    p.add_argument(
        "--load-transcripts",
        action="store_true",
        help="Fetch captions/transcripts during load (default: skip for faster catalog ingestion)",
    )
    p.add_argument(
        "--transcript-delay",
        type=float,
        default=6.0,
        help="Seconds between transcript fetches when --load-transcripts is enabled",
    )
    p.add_argument(
        "--cookies",
        default="",
        help="Path to YouTube cookies.txt for transcript fetches",
    )
    p.add_argument(
        "--proxy",
        default="",
        help="Optional proxy URL for transcript fetches",
    )
    args = p.parse_args()

    path = Path(args.input).expanduser().resolve()
    if not path.exists():
        print(f"ERROR: input CSV not found: {path}")
        return 2

    rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
    loaded_ok = 0
    skipped_no_channel = 0
    failed = 0

    for r in rows:
        jid = (r.get("jurisdiction_id") or "").strip()
        name = (r.get("county_name") or r.get("jurisdiction_name") or "").strip()
        cid = (r.get("channel_id") or "").strip()
        curl = (r.get("channel_url") or "").strip() or f"https://www.youtube.com/channel/{cid}"
        ctitle = (r.get("channel_title") or "").strip() or name
        discovery_method = (r.get("discovery_method") or "").strip() or "fallback_discovery"
        source_priority = (r.get("source_priority") or "").strip() or "fallback_discovery"

        raw_confidence = (
            (r.get("confidence_score") or "").strip()
            or (r.get("confidence") or "").strip()
        )
        confidence_args: list[str] = []
        if raw_confidence:
            try:
                confidence = float(raw_confidence)
                confidence_args = ["--confidence-score", str(confidence)]
            except ValueError:
                confidence_args = []

        if not (jid and name and cid):
            skipped_no_channel += 1
            continue

        cmd = [
            args.python,
            "packages/scrapers/src/scrapers/youtube/load_youtube_for_jurisdiction.py",
            "--jurisdiction-id",
            jid,
            "--jurisdiction-name",
            name,
            "--state",
            args.state,
            "--jurisdiction-type",
            args.jurisdiction_type,
            "--channel-id",
            cid,
            "--channel-title",
            ctitle,
            "--channel-url",
            curl,
            "--discovery-method",
            discovery_method,
            "--source-priority",
            source_priority,
            "--max-videos",
            str(args.max_videos),
            "--min-duration-seconds",
            str(args.min_duration_seconds),
            "--force",
        ] + confidence_args

        if args.load_transcripts:
            cmd += ["--transcript-delay", str(args.transcript_delay)]
            if args.cookies.strip():
                cmd += ["--cookies", args.cookies.strip()]
            if args.proxy.strip():
                cmd += ["--proxy", args.proxy.strip()]
        else:
            cmd += ["--skip-transcripts"]

        rc = subprocess.run(cmd).returncode
        if rc == 0:
            loaded_ok += 1
        else:
            failed += 1

    print({
        "loaded_ok": loaded_ok,
        "skipped_no_channel": skipped_no_channel,
        "failed": failed,
    })

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
