#!/usr/bin/env python3
"""Validate ```mermaid fences in one Markdown file (alias for validate_mermaid_reports)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from llm.gemini.mermaid_validate import (
    format_report,
    mermaid_cli_available,
    repair_and_validate_markdown,
    validate_markdown_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    if not mermaid_cli_available():
        print("Run: cd website && npm install", file=sys.stderr)
        return 2
    if args.repair:
        report = repair_and_validate_markdown(args.markdown.resolve(), write=True)
    else:
        report = validate_markdown_file(args.markdown.resolve())
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
