"""CLI flag defaults for meta_gate_validate (no live DB/Jev)."""

from __future__ import annotations

from llm.typesafe.meta_gate_validate import build_parser
from llm.typesafe.meta_gate_sample import DEFAULT_SEED


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.seed == DEFAULT_SEED
    assert args.n_final == 1000
    assert args.n_pool == 2500
    assert args.states is None
    assert args.dry_run is False
    assert args.skip_screen is False


def test_parser_overrides():
    args = build_parser().parse_args(
        ["--seed", "1", "--n-final", "20", "--n-pool", "50", "--states", "AL,GA", "--dry-run"]
    )
    assert args.seed == 1
    assert args.n_final == 20
    assert args.n_pool == 50
    assert args.states == "AL,GA"
    assert args.dry_run is True
