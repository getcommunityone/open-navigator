"""
Shared helpers for notebooks under ``scripts/colab/``.

Supports **Google Colab** (Drive mount + ``CommunityOne/`` layout) and **local Jupyter /
VS Code** (repo checkout on ``sys.path``, pipeline data under ``data/`` in the repo).
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path


def in_colab() -> bool:
    try:
        import google.colab  # noqa: F401

        return True
    except ImportError:
        return False


def repo_root_from_this_file() -> Path:
    """``open-navigator`` root: ``.../scripts/colab/colab_paths.py`` → ``parents[2]``."""
    return Path(__file__).resolve().parents[2]


# Drive-side candidate locations probed in Colab when GOVERNANCE_PIPELINE_DATA_ROOT is unset.
# Order matters: the first directory that exists wins.
_COLAB_DRIVE_CANDIDATES_REL = (
    "MyDrive/CommunityOne/hackathons/2026_Gemma_4_Good",
    "MyDrive/CommunityOne/governance_pipeline_data",
)
_COLAB_SHARED_GLOBS_REL = (
    "Shareddrives/*/CommunityOne/hackathons/2026_Gemma_4_Good",
    "Shareddrives/*/CommunityOne/governance_pipeline_data",
)


def _colab_drive_candidates(mount_point: str = "/content/drive") -> list[Path]:
    """Ordered list of plausible governance-pipeline data roots under a mounted Drive."""
    mount = Path(mount_point)
    out: list[Path] = [mount / rel for rel in _COLAB_DRIVE_CANDIDATES_REL]
    for pattern in _COLAB_SHARED_GLOBS_REL:
        out.extend(sorted(Path(p) for p in glob.glob(str(mount / pattern))))
    return out


@dataclass(frozen=True)
class NotebookLayoutPaths:
    """Paths returned by :func:`setup_notebook_paths`."""

    in_colab: bool
    project_path: Path
    governance_pipeline_data: Path


def setup_notebook_paths(mount_point: str = "/content/drive") -> NotebookLayoutPaths:
    """
    Resolve repo root and the governance pipeline data directory.

    - **project_path** — ``open-navigator`` root (prompts, ``scripts.utils.gdrive_paths``, etc.).
      Taken from the location of this file (works when the notebook runs from the checkout).
    - **governance_pipeline_data** — root containing ``01_raw_inputs``, ``02_reference_data``,
      ``03_processed_outputs``:

      - **Colab**:

        1. ``GOVERNANCE_PIPELINE_DATA_ROOT`` env var (absolute path) wins if set.
        2. Otherwise probe ``/content/drive/MyDrive/CommunityOne/hackathons/2026_Gemma_4_Good``
           and ``/content/drive/MyDrive/CommunityOne/governance_pipeline_data`` (in that order),
           then matching ``Shareddrives/*/CommunityOne/…`` paths. First existing dir wins.
        3. Fallback: the first candidate above (so callers get a clear "missing"
           error referencing the expected Drive path, not a meaningless ``/content/`` sibling).
      - **Local**: ``<repo>/data/governance_pipeline_data`` (under gitignored ``data/``),
        unless ``GOVERNANCE_PIPELINE_DATA_ROOT`` is set to an absolute path.
    """
    repo = repo_root_from_this_file()
    explicit = (os.getenv("GOVERNANCE_PIPELINE_DATA_ROOT") or "").strip()
    if in_colab():
        if explicit:
            return NotebookLayoutPaths(True, repo, Path(explicit).expanduser())
        candidates = _colab_drive_candidates(mount_point)
        for cand in candidates:
            if cand.is_dir():
                return NotebookLayoutPaths(True, repo, cand)
        # Nothing matched — return the first candidate so the downstream "missing"
        # error names a real Drive path the user can create or correct.
        fallback = candidates[0] if candidates else (repo.parent / "governance_pipeline_data")
        return NotebookLayoutPaths(True, repo, fallback)
    if explicit:
        return NotebookLayoutPaths(False, repo, Path(explicit).expanduser().resolve())
    return NotebookLayoutPaths(False, repo, repo / "data" / "governance_pipeline_data")


def maybe_mount_google_drive(mount_point: str = "/content/drive") -> None:
    """Call ``drive.mount`` only when running inside Google Colab."""
    if not in_colab():
        return
    from google.colab import drive

    drive.mount(mount_point)
