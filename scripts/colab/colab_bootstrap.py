"""
Notebook §1 bootstrap: locate ``open-navigator``, refresh from GitHub, mount Drive.

Colab often opens only the ``.ipynb`` file (not the full repo). The §1 code cell
therefore clones to ``/content/open-navigator`` before importing project modules.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Tuple

_REPO_MARKER = Path("scripts") / "colab" / "colab_paths.py"
_DEFAULT_COLAB_CLONE = Path("/content/open-navigator")
_CLONE_URL = "https://github.com/getcommunityone/open-navigator.git"
_EPHEMERAL_DATA_DIR = Path("/content/_ephemeral_colab_pipeline_shell")


def _in_colab() -> bool:
    try:
        import google.colab  # noqa: F401

        return True
    except ImportError:
        return False


def _is_repo_root(path: Path) -> bool:
    return (path / _REPO_MARKER).is_file()


def discover_repo_root(
    *,
    clone_if_colab: bool = True,
    colab_clone_dir: Path | None = None,
) -> Path:
    """
    Resolve the ``open-navigator`` repository root.

    Order: ``OPEN_NAVIGATOR_ROOT`` → ``/content/open-navigator`` → walk ``cwd``
    parents → ``git clone`` on Colab when ``clone_if_colab``.
    """
    env = (os.environ.get("OPEN_NAVIGATOR_ROOT") or "").strip()
    if env:
        root = Path(env).expanduser().resolve()
        if _is_repo_root(root):
            return root

    colab_dest = (colab_clone_dir or _DEFAULT_COLAB_CLONE).resolve()
    candidates: list[Path] = [colab_dest, Path.cwd().resolve(), *Path.cwd().resolve().parents]

    seen: set[Path] = set()
    for anchor in candidates:
        if anchor in seen:
            continue
        seen.add(anchor)
        if _is_repo_root(anchor):
            return anchor.resolve()

    should_clone = clone_if_colab and (_in_colab() or str(colab_dest).startswith("/content"))
    if should_clone:
        if _is_repo_root(colab_dest):
            return colab_dest
        if colab_dest.exists() and not _is_repo_root(colab_dest):
            raise RuntimeError(
                f"{colab_dest} exists but is not open-navigator (missing {_REPO_MARKER}). "
                "Remove that folder or set OPEN_NAVIGATOR_ROOT to your checkout."
            )
        print("Downloading open-navigator from GitHub (one-time per Colab session)…")
        rc = os.system(f"git clone {_CLONE_URL} {colab_dest}")
        if rc != 0:
            raise RuntimeError(f"git clone failed (exit {rc})")
        if _is_repo_root(colab_dest):
            return colab_dest

    raise RuntimeError(
        "Could not find the open-navigator repository.\n\n"
        "What to do:\n"
        "  • Google Colab: open\n"
        "      https://colab.research.google.com/github/getcommunityone/open-navigator/blob/main/scripts/colab/02_run_meeting_llm.ipynb\n"
        "    then re-run §1 (it clones to /content/open-navigator).\n"
        "  • Cursor / local Jupyter: in the cell below §1, set:\n"
        "      import os\n"
        "      os.environ['OPEN_NAVIGATOR_ROOT'] = '/absolute/path/to/open-navigator'\n"
        "    then re-run §1.\n"
        "  • Do not use a stale copy of 03_run_meeting_llm.ipynb — use 02_run_meeting_llm.ipynb.\n"
    )


def bootstrap_repo(
    *,
    clone_if_colab: bool = True,
    set_open_navigator_root: bool = True,
) -> Path:
    """Discover repo and insert it on ``sys.path``."""
    root = discover_repo_root(clone_if_colab=clone_if_colab)
    if set_open_navigator_root:
        os.environ.setdefault("OPEN_NAVIGATOR_ROOT", str(root))
    for entry in (str(root), str(root / "scripts" / "colab")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return root


def _git_refresh(repo: Path, *, run_git_update: bool = True) -> None:
    if not run_git_update or not (repo / ".git").is_dir():
        return
    print("Updating open-navigator from GitHub (main)…")
    rc = os.system(
        f"cd {repo} && git config core.hooksPath /dev/null "
        "&& git fetch origin && git reset --hard origin/main"
    )
    if rc != 0:
        print(f"Warning: git update exited {rc} — continuing with files on disk.")


def _clear_stale_imports() -> None:
    for name in list(sys.modules):
        if name.startswith("scripts.colab") or name.startswith("scripts.utils.gdrive_paths"):
            sys.modules.pop(name, None)
    for name in ("demo_scope", "pipeline_media_scope", "colab_bootstrap"):
        sys.modules.pop(name, None)
    stale = os.environ.pop("GOVERNANCE_PIPELINE_DATA_ROOT", None)
    if stale:
        print(f"Cleared stale GOVERNANCE_PIPELINE_DATA_ROOT={stale}")


def _remove_ephemeral_colab_shell() -> None:
    if _EPHEMERAL_DATA_DIR.is_dir():
        print(
            f"Removing empty scratch folder {_EPHEMERAL_DATA_DIR} "
            "(real outputs live on Google Drive)."
        )
        shutil.rmtree(_EPHEMERAL_DATA_DIR, ignore_errors=True)


def print_bootstrap_summary(paths: Any) -> None:
    """Judge-friendly confirmation that §1 succeeded."""
    where = "Google Colab" if paths.in_colab else "Local Jupyter"
    print()
    print("=" * 60)
    print("§1 Bootstrap OK — you can continue to §2")
    print("=" * 60)
    print(f"Environment:     {where}")
    print(f"Code (repo):     {paths.project_path}")
    print(f"Hackathon data:  {paths.governance_pipeline_data}")
    if paths.in_colab:
        print()
        print("Judges: confirm the hackathon path is under your Drive, e.g.")
        print("  My Drive/CommunityOne/hackathons/2026_Gemma_4_Good")
        print("not a path that starts with /content/ only.")
    print("=" * 60)


def complete_section1_bootstrap(
    repo: Path | None = None,
    *,
    run_git_update: bool = True,
) -> Tuple[Path, Any]:
    """
    Git refresh, Drive mount, resolve hackathon data root, print summary.

    Pass ``repo`` when §1 already cloned or discovered the checkout; otherwise
    calls :func:`bootstrap_repo`.

    Returns ``(repo_path, paths)`` where ``paths`` is a :class:`NotebookLayoutPaths`.
    """
    repo_path = (repo or bootstrap_repo()).resolve()
    os.environ.setdefault("OPEN_NAVIGATOR_ROOT", str(repo_path))
    for entry in (str(repo_path), str(repo_path / "scripts" / "colab")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    _dotenv = repo_path / ".env"
    if _dotenv.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(_dotenv, override=False)
        except ImportError:
            pass
    _git_refresh(repo_path, run_git_update=run_git_update)
    _clear_stale_imports()
    _remove_ephemeral_colab_shell()

    from scripts.colab.colab_paths import maybe_mount_google_drive, setup_notebook_paths

    maybe_mount_google_drive()
    try:
        paths = setup_notebook_paths()
    except RuntimeError as exc:
        print("\nCould not find hackathon data on Google Drive.\n")
        print(str(exc))
        print("\nDrive folders visible from this session:")
        for probe in (
            Path("/content/drive"),
            Path("/content/drive/MyDrive"),
            Path("/content/drive/MyDrive/CommunityOne"),
            Path("/content/drive/MyDrive/CommunityOne/hackathons"),
        ):
            if probe.is_dir():
                names = sorted(p.name for p in probe.iterdir())[:15]
                print(f"  {probe}: {names}")
            else:
                print(f"  {probe}: (not mounted)")
        raise
    print_bootstrap_summary(paths)
    return repo_path, paths


def notebook_section1_cell() -> Tuple[Path, Any]:
    """Single entry point for §1 notebook cells."""
    return complete_section1_bootstrap()
