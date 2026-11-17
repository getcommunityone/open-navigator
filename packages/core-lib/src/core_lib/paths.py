"""Locate the open-navigator repository root from any workspace module.

Package modules live at different depths (``packages/<pkg>/src/<pkg>/<sub>/<mod>.py``),
so hardcoding ``Path(__file__).parents[N]`` is fragile: an off-by-two lands in
``packages/<pkg>`` and silently writes caches to the wrong ``data/`` tree (#458).
Use :func:`repo_root` instead.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Environment variable that overrides discovery (absolute path to the repo root).
REPO_ROOT_ENV = "OPEN_NAVIGATOR_REPO_ROOT"

#: A directory is the repo root when it holds this marker file.
REPO_ROOT_MARKER = "AGENTS.md"


def _is_repo_root(path: Path) -> bool:
    if (path / REPO_ROOT_MARKER).is_file():
        return True
    pyproject = path / "pyproject.toml"
    if pyproject.is_file():
        try:
            return "[tool.uv.workspace]" in pyproject.read_text(encoding="utf-8")
        except OSError:
            return False
    return False


def find_repo_root(start: str | os.PathLike[str] | None = None) -> Path | None:
    """Walk up from ``start`` (a file or directory) to the repo root, or ``None``."""
    if start is None:
        return None
    here = Path(start).resolve()
    if here.is_file() or not here.exists():
        here = here.parent
    for candidate in (here, *here.parents):
        if _is_repo_root(candidate):
            return candidate
    return None


def repo_root(start: str | os.PathLike[str] | None = None) -> Path:
    """Return the open-navigator repo root (the directory containing ``AGENTS.md``).

    Resolution order: ``$OPEN_NAVIGATOR_REPO_ROOT``, then walking up from ``start``
    (pass ``__file__``), then from this module, then from the current directory.
    Falls back to the current directory when no marker is found (e.g. a wheel
    installed outside a checkout).
    """
    override = os.getenv(REPO_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    for origin in (start, __file__, Path.cwd()):
        found = find_repo_root(origin)
        if found is not None:
            return found
    return Path.cwd().resolve()
