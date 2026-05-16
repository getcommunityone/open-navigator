"""
Shared helpers for notebooks under ``scripts/colab/``.

Supports **Google Colab** (Drive mount + ``CommunityOne/`` layout) and **local Jupyter /
VS Code** (repo checkout on ``sys.path``, pipeline data under ``data/`` in the repo).
"""
from __future__ import annotations

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


@dataclass(frozen=True)
class NotebookLayoutPaths:
    """Paths returned by :func:`setup_notebook_paths`."""

    in_colab: bool
    project_path: Path
    governance_pipeline_data: Path


def setup_notebook_paths() -> NotebookLayoutPaths:
    """
    Resolve repo root and the governance pipeline data directory.

    - **project_path** — ``open-navigator`` root (prompts, ``scripts.utils.gdrive_paths``, etc.).
      Taken from the location of this file (works when the notebook runs from the checkout).
    - **governance_pipeline_data** — root containing ``01_raw_inputs``, ``02_reference_data``,
      ``03_processed_outputs``:

      - **Colab** (recommended layout): sibling of the repo under the same parent directory,
        e.g. ``.../CommunityOne/governance_pipeline_data`` next to
        ``.../CommunityOne/open-navigator``.
      - **Local**: ``<repo>/data/governance_pipeline_data`` (under gitignored ``data/``),
        unless ``GOVERNANCE_PIPELINE_DATA_ROOT`` is set to an absolute path.
    """
    repo = repo_root_from_this_file()
    if in_colab():
        return NotebookLayoutPaths(True, repo, repo.parent / "governance_pipeline_data")
    explicit = (os.getenv("GOVERNANCE_PIPELINE_DATA_ROOT") or "").strip()
    if explicit:
        return NotebookLayoutPaths(False, repo, Path(explicit).expanduser().resolve())
    return NotebookLayoutPaths(False, repo, repo / "data" / "governance_pipeline_data")


def maybe_mount_google_drive(mount_point: str = "/content/drive") -> None:
    """Call ``drive.mount`` only when running inside Google Colab."""
    if not in_colab():
        return
    from google.colab import drive

    drive.mount(mount_point)
