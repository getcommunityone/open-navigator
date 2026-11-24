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


def analysis_file_usable(path: Path) -> bool:
    """True when a saved analysis file can count as "already analysed" (#825).

    An interrupted run can leave an empty or truncated file. Treating that as done means the meeting
    is never analysed and the loader reports the same unreadable file on every run. Only the start
    of the file is read, because this runs once per video over thousands of files: the file must
    exist, hold something, and begin with a JSON object.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(256)
    except OSError:
        return False
    return head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"{")
