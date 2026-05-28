#!/usr/bin/env python3
"""
Rewrite ``data/cache/leagueofcities/*/cities.json`` — set junk ``website`` values to null.

Usage (repo root):
  .venv/bin/python scripts/datasources/leagueofcities/sanitize_league_cache_websites.py
  .venv/bin/python scripts/datasources/leagueofcities/sanitize_league_cache_websites.py --states AL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.datasources.leagueofcities.league_website_sanitize import sanitize_league_website

CACHE = _ROOT / "data" / "cache" / "leagueofcities"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--states", nargs="*", help="USPS codes (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    states = {s.upper() for s in args.states} if args.states else None
    nulled = 0
    files = 0
    for path in sorted(CACHE.glob("*/cities.json")):
        st = path.parent.name.upper()
        if states and st not in states:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        cities = doc.get("cities")
        if not isinstance(cities, list):
            continue
        changed = False
        for c in cities:
            if not isinstance(c, dict):
                continue
            old = c.get("website")
            new = sanitize_league_website(old)
            if old != new:
                c["website"] = new
                changed = True
                if old and not new:
                    nulled += 1
        if changed and not args.dry_run:
            path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            files += 1
        elif changed:
            files += 1
    print(f"{'Would update' if args.dry_run else 'Updated'} {files} file(s); nulled {nulled} website(s)")


if __name__ == "__main__":
    main()
