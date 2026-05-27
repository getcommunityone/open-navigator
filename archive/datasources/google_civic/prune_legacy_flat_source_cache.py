#!/usr/bin/env python3
"""Delete pre-folder Google Civic / Ballotpedia cache JSON (flat under {state}/{type}/)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.datasources.google_civic.load_google_civic_officials_to_c1 import (  # noqa: E402
    prune_legacy_flat_source_cache,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print paths only; do not delete")
    args = parser.parse_args(argv)
    n = prune_legacy_flat_source_cache(dry_run=args.dry_run)
    action = "Would delete" if args.dry_run else "Deleted"
    print(f"{action} {n} legacy flat cache file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
