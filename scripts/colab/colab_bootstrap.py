"""
Find ``open-navigator`` and put it on ``sys.path`` before importing ``colab_paths``.

Used by Colab notebook §1 cells. Safe to import only after ``scripts/colab`` is on
``sys.path``, or call :func:`discover_repo_root` standalone (stdlib only).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_MARKER = Path("scripts") / "colab" / "colab_paths.py"
_DEFAULT_COLAB_CLONE = Path("/content/open-navigator")
_CLONE_URL = "https://github.com/getcommunityone/open-navigator.git"


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

    Order: ``OPEN_NAVIGATOR_ROOT`` → ``/content/open-navigator`` → walk ``cwd`` parents
    → git clone on Colab when ``clone_if_colab``.
    """
    env = (os.environ.get("OPEN_NAVIGATOR_ROOT") or "").strip()
    if env:
        root = Path(env).expanduser().resolve()
        if _is_repo_root(root):
            return root

    colab_dest = (colab_clone_dir or _DEFAULT_COLAB_CLONE).resolve()
    candidates: list[Path] = []
    if colab_dest not in candidates:
        candidates.append(colab_dest)

    here = Path.cwd().resolve()
    candidates.append(here)
    candidates.extend(here.parents)

    seen: set[Path] = set()
    for anchor in candidates:
        if anchor in seen:
            continue
        seen.add(anchor)
        if _is_repo_root(anchor):
            return anchor.resolve()

    if clone_if_colab and _in_colab():
        if _is_repo_root(colab_dest):
            return colab_dest
        if colab_dest.exists() and not _is_repo_root(colab_dest):
            raise RuntimeError(
                f"{colab_dest} exists but is not open-navigator "
                f"(missing {_REPO_MARKER})"
            )
        print(f"Cloning open-navigator into {colab_dest}…")
        rc = os.system(f"git clone {_CLONE_URL} {colab_dest}")
        if rc != 0:
            raise RuntimeError(f"git clone failed (exit {rc})")
        if _is_repo_root(colab_dest):
            return colab_dest

    raise RuntimeError(
        "Could not find open-navigator (scripts/colab/colab_paths.py).\n\n"
        "Fix one of:\n"
        "  • Colab: re-run §1 (clones to /content/open-navigator), or open "
        "02_run_meeting_llm.ipynb from GitHub.\n"
        "  • Local / Cursor: set before §1:\n"
        "      import os\n"
        "      os.environ['OPEN_NAVIGATOR_ROOT'] = '/path/to/open-navigator'\n"
        "  • Or start Jupyter with kernel cwd at the repo root "
        "(folder that contains scripts/colab/).\n"
    )


def bootstrap_repo(
    *,
    clone_if_colab: bool = True,
    set_open_navigator_root: bool = True,
) -> Path:
    """Discover repo, optional ``OPEN_NAVIGATOR_ROOT``, insert root on ``sys.path``."""
    root = discover_repo_root(clone_if_colab=clone_if_colab)
    if set_open_navigator_root:
        os.environ.setdefault("OPEN_NAVIGATOR_ROOT", str(root))
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    colab_dir = root / "scripts" / "colab"
    cs = str(colab_dir)
    if colab_dir.is_dir() and cs not in sys.path:
        sys.path.insert(0, cs)
    return root
