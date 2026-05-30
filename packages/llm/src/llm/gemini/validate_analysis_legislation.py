#!/usr/bin/env python3
"""Validate/fix legislation_refs in a Part 1 analysis JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.gemini.legislation_analysis import (  # noqa: E402
    enrich_part1_legislation,
    validate_and_fix_legislation_refs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_json", type=Path)
    parser.add_argument("--write", action="store_true", help="Overwrite file with fixed JSON")
    parser.add_argument("--agenda", action="store_true", help="Also run agenda→leg_id ingest")
    args = parser.parse_args()

    data = json.loads(args.analysis_json.read_text(encoding="utf-8"))
    if args.agenda:
        data = enrich_part1_legislation(data)
        report = data.get("_legislation_validation") or data.get("_agenda_legislation_ingest")
    else:
        data, report = validate_and_fix_legislation_refs(data, fix=True)

    print(json.dumps(report, indent=2))
    if args.write:
        args.analysis_json.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.analysis_json}")


if __name__ == "__main__":
    main()
