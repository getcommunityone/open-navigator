"""File names that carry the analysis tier (#796). Pure string logic, no imports from the pipeline."""

from __future__ import annotations

from pathlib import Path


def meta_with_tier_suffix(meta_path: Path, tier: str) -> Path:
    """``<stem>.meta.json`` for light, ``<stem>_full.meta.json`` for full.

    The analysis and report files already carry the tier in their names. The run metadata did not,
    so a full run overwrote the light run's record of its model, prompt and token usage. This
    matches ``meta_path_for_analysis`` for a ``<stem>_full.json`` analysis file.
    """
    if tier != "full":
        return meta_path
    name = meta_path.name
    suffix = ".meta.json"
    if not name.endswith(suffix):
        return meta_path
    stem = name[: -len(suffix)]
    if stem.endswith("_full"):
        return meta_path
    return meta_path.with_name(f"{stem}_full{suffix}")
