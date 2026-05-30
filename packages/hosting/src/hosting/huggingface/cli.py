"""Unified CLI for HuggingFace dataset publishing and Space deployment.

Run as ``on-hf <command>`` (console script) or
``python -m hosting.huggingface <command>``.

Commands:
    gold           Publish consolidated gold parquet files (data/gold/*.parquet)
    national       Publish national-level gold datasets (data/gold/national)
    meetings       Publish meeting gold tables
    contacts       Publish contacts gold tables
    nonprofits     Publish nonprofit gold tables
    state-splits   Publish per-state split files
    discovery      Publish combined discovery CSVs as one dataset
    deploy-space   Deploy the repo to a HuggingFace Space
    check-vars     Check required HuggingFace environment variables
    check-space    Inspect a HuggingFace Space's configuration
"""

from __future__ import annotations

import argparse
import sys

from loguru import logger

from .config import HFConfig, HFConfigError
from . import datasets as ds
from . import spaces
from .publisher import DatasetPublisher, summarize


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="on-hf",
        description="Publish Open Navigator datasets to HuggingFace and deploy Spaces.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_private(p: argparse.ArgumentParser) -> None:
        p.add_argument("--private", action="store_true", help="Make dataset(s) private")

    # gold (consolidated)
    p = sub.add_parser("gold", help="Publish consolidated gold parquet files")
    p.add_argument("--gold-dir", default=str(ds.DEFAULT_GOLD_DIR))
    p.add_argument("--file", dest="only_file", help="Upload only this file")
    p.add_argument("--max-rows", type=int, help="Limit rows per file (testing)")
    p.add_argument("--skip-large", action="store_true", help="Skip files > 100 MB")
    add_private(p)

    # national
    p = sub.add_parser("national", help="Publish national-level gold datasets")
    p.add_argument("--gold-dir", default=str(ds.DEFAULT_NATIONAL_DIR))
    add_private(p)

    # per-family table groups
    for cmd, helptext in (
        ("meetings", "Publish meeting gold tables"),
        ("contacts", "Publish contacts gold tables"),
        ("nonprofits", "Publish nonprofit gold tables"),
    ):
        p = sub.add_parser(cmd, help=helptext)
        p.add_argument("--gold-dir", default=str(ds.DEFAULT_GOLD_DIR))
        p.add_argument(
            "--only", nargs="+", help="Only these table names (default: all)"
        )
        add_private(p)

    # state-splits
    p = sub.add_parser("state-splits", help="Publish per-state split files")
    p.add_argument("--splits-dir", default=str(ds.DEFAULT_STATE_SPLITS_DIR))
    p.add_argument("--state", help="A single state (e.g. AL)")
    p.add_argument("--states", nargs="+", help="Multiple states")
    p.add_argument("--all", action="store_true", help="All available states")
    p.add_argument("--dry-run", action="store_true")
    add_private(p)

    # discovery
    p = sub.add_parser("discovery", help="Publish combined discovery CSVs")
    p.add_argument("--repo", required=True, help="Full repo id, e.g. org/name")
    p.add_argument("--data-dir", default="data/bronze/discovered_sources")
    add_private(p)

    # deploy-space
    p = sub.add_parser("deploy-space", help="Deploy the repo to a HuggingFace Space")
    p.add_argument("--space-id", default=spaces.DEFAULT_SPACE_ID)
    p.add_argument("--folder", default=".")
    p.add_argument("--dry-run", action="store_true")

    # check-vars / check-space
    sub.add_parser("check-vars", help="Check required HuggingFace env vars")
    p = sub.add_parser("check-space", help="Inspect a Space's configuration")
    p.add_argument("--space-id", default="CommunityOne/www.communityone.com")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = HFConfig()

    # Commands that don't need a logged-in publisher.
    if args.command == "check-vars":
        return 0 if spaces.check_env_vars() else 1
    if args.command == "check-space":
        spaces.check_space_vars(args.space_id, config)
        return 0
    if args.command == "deploy-space":
        try:
            deployer = spaces.SpaceDeployer(config)
            deployer.deploy_folder(
                args.space_id, args.folder, dry_run=args.dry_run
            )
        except HFConfigError as exc:
            logger.error(str(exc))
            return 1
        return 0

    # Dataset-publishing commands.
    try:
        publisher = DatasetPublisher(config)
    except HFConfigError as exc:
        logger.error(str(exc))
        return 1

    if args.command == "gold":
        results = ds.publish_gold_dir(
            publisher,
            config=config,
            gold_dir=args.gold_dir,
            only_file=args.only_file,
            max_rows=args.max_rows,
            skip_large=args.skip_large,
            private=args.private,
        )
    elif args.command == "national":
        results = ds.publish_national_gold(
            publisher, config=config, gold_dir=args.gold_dir, private=args.private
        )
    elif args.command == "meetings":
        results = ds.publish_meetings(
            publisher, config=config, gold_dir=args.gold_dir,
            only=args.only, private=args.private,
        )
    elif args.command == "contacts":
        results = ds.publish_contacts(
            publisher, config=config, gold_dir=args.gold_dir,
            only=args.only, private=args.private,
        )
    elif args.command == "nonprofits":
        results = ds.publish_nonprofits(
            publisher, config=config, gold_dir=args.gold_dir,
            only=args.only, private=args.private,
        )
    elif args.command == "discovery":
        result = ds.publish_discovery(
            publisher, args.repo, data_dir=args.data_dir, private=args.private
        )
        results = [result]
    elif args.command == "state-splits":
        states = None
        if args.state:
            states = [args.state]
        elif args.states:
            states = args.states
        elif not args.all:
            parser.error("state-splits requires --all, --state, or --states")
        state_results = ds.publish_state_splits(
            publisher,
            config=config,
            splits_dir=args.splits_dir,
            states=states,
            dry_run=args.dry_run,
            private=args.private,
        )
        ok = sum(1 for v in state_results.values() if v)
        logger.info("State splits: {}/{} states OK", ok, len(state_results))
        return 0 if ok == len(state_results) else 1
    else:  # pragma: no cover - argparse enforces choices
        parser.error(f"Unknown command: {args.command}")

    _, failed, _ = summarize(results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
