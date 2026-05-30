"""Repo discovery for Colab notebooks."""

from __future__ import annotations

from pathlib import Path


from llm.governance.colab_bootstrap import discover_repo_root


def test_discover_repo_root_from_env(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("OPEN_NAVIGATOR_ROOT", str(root))
    assert discover_repo_root(clone_if_colab=False) == root.resolve()


def test_discover_repo_root_walk_cwd(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("OPEN_NAVIGATOR_ROOT", raising=False)
    monkeypatch.chdir(root / "packages" / "llm" / "src" / "llm" / "governance")
    assert discover_repo_root(clone_if_colab=False) == root.resolve()
