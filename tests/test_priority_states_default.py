"""The packaged DEFAULT_PRIORITY_STATES must equal the legacy scrape_priority_states value."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module_constant(path: Path, name: str) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"{name} not assigned at module level in {path}")


def test_youtube_loader_priority_states_match_legacy_value() -> None:
    legacy = _module_constant(
        ROOT / "scripts" / "datasources" / "jurisdiction_pilot" / "scrape_priority_states.py",
        "DEFAULT_PRIORITY_STATES",
    )
    packaged = _module_constant(
        ROOT / "packages" / "scrapers" / "src" / "scrapers" / "youtube" / "load_youtube_events_to_postgres.py",
        "DEFAULT_PRIORITY_STATES",
    )
    assert packaged == legacy == ("AL", "GA", "IN", "MA", "WA", "WI")
