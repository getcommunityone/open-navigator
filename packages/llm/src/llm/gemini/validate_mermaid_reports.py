#!/usr/bin/env python3
"""
Validate Mermaid in Part 2 reports (single file, one jurisdiction folder, or repo-wide).

  cd website && npm install   # once

  # One report
  .venv/bin/python -m llm.gemini.validate_mermaid_reports \\
      data/cache/gemini_transcript_policy/municipality_0177256/03_reports/foo.md

  # All reports for Tuscaloosa (repair sanitizer, then validate)
  .venv/bin/python -m llm.gemini.validate_mermaid_reports \\
      --jurisdiction-id municipality_0177256 --repair

  # CI: exit 1 if any diagram fails
  .venv/bin/python -m llm.gemini.validate_mermaid_reports \\
      --jurisdiction-id municipality_0177256 --strict
"""

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
from llm.gemini.transcript_cache_paths import DIR_REPORTS, jurisdiction_root

_DEFAULT_CACHE = _REPO / "data/cache/gemini_transcript_policy"


def _report_paths(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: str = "",
) -> list[Path]:
    st = (state_code or "").strip().upper() or None
    reports_dir = jurisdiction_root(
        cache_dir, jurisdiction_id, state_code=st
    ) / DIR_REPORTS
    if not reports_dir.is_dir():
        return []
    return sorted(
        p
        for p in reports_dir.glob("*.md")
        if p.is_file() and not p.name.endswith(".diagrams.md")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "markdown",
        nargs="?",
        type=Path,
        help="Single report .md (optional if --jurisdiction-id)",
    )
    parser.add_argument(
        "--jurisdiction-id",
        default="",
        help=f"Validate all 03_reports/*.md under cache (default folder: {_DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--state",
        default="",
        help="Two-letter state for geographic cache layout (e.g. AL)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE,
        help="gemini_transcript_policy cache root",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Run mermaid_diagrams sanitizer on each file before validating",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when any diagram fails (for CI)",
    )
    parser.add_argument(
        "--write-sidecars",
        action="store_true",
        help="Write .mermaid-errors.json next to each failing report",
    )
    args = parser.parse_args()

    if not mermaid_cli_available():
        print("Missing website/node_modules/mermaid. Run: cd website && npm install", file=sys.stderr)
        return 2

    paths: list[Path] = []
    if args.markdown:
        paths = [args.markdown.resolve()]
    elif args.jurisdiction_id.strip():
        paths = _report_paths(
            args.cache_dir.resolve(),
            args.jurisdiction_id.strip(),
            state_code=(args.state or "").strip(),
        )
    else:
        parser.error("Pass a report .md path or --jurisdiction-id")

    if not paths:
        print("No report .md files found.", file=sys.stderr)
        return 1

    failed = 0
    for path in paths:
        if not path.is_file():
            print(f"SKIP  missing: {path}", file=sys.stderr)
            failed += 1
            continue
        if args.repair:
            report = repair_and_validate_markdown(path, write=True)
        else:
            report = validate_markdown_file(path)
        print(format_report(report))
        if not report.ok:
            failed += 1
            if args.write_sidecars:
                from llm.gemini.mermaid_validate import write_errors_sidecar

                write_errors_sidecar(report, path.with_suffix(path.suffix + ".mermaid-errors.json"))
        print()

    if failed and args.strict:
        return 1
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
