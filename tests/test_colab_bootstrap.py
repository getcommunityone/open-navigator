"""Repo discovery for Colab notebooks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_COLAB = Path(__file__).resolve().parents[1] / "scripts" / "colab"
if str(_COLAB) not in sys.path:
    sys.path.insert(0, str(_COLAB))

from colab_bootstrap import bootstrap_repo, discover_repo_root  # noqa: E402


def test_discover_repo_root_from_env(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("OPEN_NAVIGATOR_ROOT", str(root))
    assert discover_repo_root(clone_if_colab=False) == root.resolve()


def test_discover_repo_root_walk_cwd(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("OPEN_NAVIGATOR_ROOT", raising=False)
    monkeypatch.chdir(root / "scripts" / "colab")
    assert discover_repo_root(clone_if_colab=False) == root.resolve()
