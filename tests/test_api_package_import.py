"""Importing one API module loads only that module, not the whole app (#261).

``api/__init__.py`` used to run ``from api.main import app``, so ``import api.database`` (or any ``api.*``
module) built the FastAPI app first: every route, the agents, the logger's file sink and telemetry. Each check runs
in a fresh interpreter, because the test session itself may already have imported ``api.main``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _modules_after(statement: str) -> set[str]:
    code = f"import sys\n{statement}\nprint('\\n'.join(sorted(sys.modules)))"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get("PYTHONPATH")]))}
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return set(done.stdout.split())


def test_importing_api_database_leaves_the_app_unloaded():
    loaded = _modules_after("import api.database")
    assert "api.database" in loaded
    assert "api.main" not in loaded


def test_importing_the_api_package_alone_loads_nothing_else():
    loaded = _modules_after("import api")
    assert not {name for name in loaded if name.startswith("api.")}
