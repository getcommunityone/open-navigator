"""CLI: python -m ingestion.mdm <address|person> [--threshold T] [--dry-run]."""

from __future__ import annotations

import argparse

from loguru import logger

from ingestion.mdm.linker import SPECS, run_linker


def main() -> None:
    parser = argparse.ArgumentParser(prog="ingestion.mdm", description=__doc__)
    parser.add_argument("entity", choices=sorted(SPECS), help="which conformed pool to resolve")
    parser.add_argument("--threshold", type=float, default=0.9, help="match probability threshold")
    parser.add_argument("--max-pairs", type=float, default=1e7, help="u-estimation sample size")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build + validate the linker/settings, then stop before any compute",
    )
    args = parser.parse_args()

    out = run_linker(
        args.entity,
        match_threshold=args.threshold,
        train_max_pairs=args.max_pairs,
        dry_run=args.dry_run,
    )
    logger.info("Done. Output: {}", out)


if __name__ == "__main__":
    main()
