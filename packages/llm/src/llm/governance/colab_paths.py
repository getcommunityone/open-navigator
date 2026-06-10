"""
Shared helpers for notebooks under ``packages/llm/src/llm/governance/``.

Supports **Google Colab** (Drive mount + hackathon layout) and **local Jupyter /
VS Code** (repo checkout on ``sys.path``, pipeline data under ``data/hackathons/``).
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path

# Single hackathon pipeline root (must match ``core_lib.gdrive_paths``).
HACKATHON_PIPELINE_ROOT_REL = Path("CommunityOne") / "hackathons" / "2026_Gemma_4_Good"


def in_colab() -> bool:
    try:
        import google.colab  # noqa: F401

        return True
    except ImportError:
        return False


def repo_root_from_this_file() -> Path:
    """``open-navigator`` root.

    ``.../packages/llm/src/llm/governance/colab_paths.py`` → ``parents[5]``.
    """
    return Path(__file__).resolve().parents[5]


def default_hackathon_pipeline_root_in_repo() -> Path:
    return repo_root_from_this_file() / "data" / "hackathons" / "2026_Gemma_4_Good"


# Colab: only ``CommunityOne/hackathons/2026_Gemma_4_Good`` (not ``governance_pipeline_data``).
_COLAB_DRIVE_CANDIDATES_REL = (
    "MyDrive/" + HACKATHON_PIPELINE_ROOT_REL.as_posix(),
)
_COLAB_SHARED_GLOBS_REL = (
    "Shareddrives/*/" + HACKATHON_PIPELINE_ROOT_REL.as_posix(),
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
    governance_pipeline_data: Path  # pipeline root (hackathon folder on Drive or in repo)


def setup_notebook_paths(mount_point: str = "/content/drive") -> NotebookLayoutPaths:
    """
    Resolve repo root and the governance pipeline data directory.

    - **project_path** — ``open-navigator`` root (prompts, ``core_lib.gdrive_paths``, etc.).
    - **governance_pipeline_data** — hackathon root with ``01_raw_inputs``, ``02_reference_data``,
      ``03_processed_outputs``:

      - **Colab**: ``GOVERNANCE_PIPELINE_DATA_ROOT`` if set, else
        ``/content/drive/MyDrive/CommunityOne/hackathons/2026_Gemma_4_Good``.
      - **Local**: ``<repo>/data/hackathons/2026_Gemma_4_Good`` unless ``GOVERNANCE_PIPELINE_DATA_ROOT`` is set.
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
        probed = "\n".join(f"  · {c}" for c in candidates) or "  (no candidates)"
        raise RuntimeError(
            "Could not locate the hackathon pipeline root on Google Drive.\n"
            f"Expected: .../CommunityOne/hackathons/2026_Gemma_4_Good\n"
            f"Probed:\n{probed}\n"
            "Fix one of:\n"
            "  1. Mount Drive and confirm that folder exists (run 01_init or copy script 01).\n"
            "  2. Set os.environ['GOVERNANCE_PIPELINE_DATA_ROOT'] to the absolute hackathon path "
            "BEFORE calling setup_notebook_paths()."
        )
    if explicit:
        return NotebookLayoutPaths(False, repo, Path(explicit).expanduser().resolve())
    # Local/WSL: prefer mounted Google Drive (same folder as Colab) when present.
    from core_lib.gdrive_paths import resolve_governance_pipeline_data_root

    pipeline_root = resolve_governance_pipeline_data_root()
    return NotebookLayoutPaths(False, repo, pipeline_root.resolve())


def maybe_mount_google_drive(mount_point: str = "/content/drive") -> None:
    """Call ``drive.mount`` only when running inside Google Colab."""
    if not in_colab():
        return
    from google.colab import drive

    drive.mount(mount_point)
