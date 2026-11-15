"""Tests for the Git LFS helpers the Hugging Face deploy sources (issue #233).

The deploy builds its commit in a clone made with GIT_LFS_SKIP_SMUDGE=1, so a file stored
in Git LFS is staged as its pointer and its object is missing from the clone's store;
git-lfs then refuses the push. These tests build that situation in temporary repositories:
one LFS file whose object can be fetched from the source repository, and one whose object
is gone everywhere.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "huggingface"
HELPER = SCRIPTS / "lfs_objects.sh"
DEPLOY = SCRIPTS / "deploy-huggingface.sh"


def _has_git_lfs() -> bool:
    if shutil.which("git") is None:
        return False
    return subprocess.run(["git", "lfs", "version"], capture_output=True).returncode == 0


needs_git_lfs = pytest.mark.skipif(not _has_git_lfs(), reason="git and git-lfs are required")


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    run_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=run_env, capture_output=True, text=True, check=True
    )
    return done.stdout


def _helper(cwd: Path, call: str) -> subprocess.CompletedProcess[str]:
    """Source the helper file in bash and run one call in ``cwd``."""
    return subprocess.run(
        ["bash", "-c", f'set -e; source "{HELPER}"; {call}'],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _oid(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture()
def deploy_clone(tmp_path: Path) -> dict[str, object]:
    """A source repo with two LFS images, and a skip-smudge clone staged like the deploy."""
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    _git(src, "config", "user.email", "test@example.com")
    _git(src, "config", "user.name", "test")
    _git(src, "lfs", "install", "--local")
    (src / ".gitattributes").write_text("*.png filter=lfs diff=lfs merge=lfs -text\n")
    kept = b"\x89PNG kept image " + os.urandom(64)
    missing = b"\x89PNG missing image " + os.urandom(64)
    (src / "img").mkdir()
    (src / "img" / "kept.png").write_bytes(kept)
    (src / "img" / "missing one.png").write_bytes(missing)
    (src / "README.md").write_text("plain text\n")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "init")

    # The second image's object is gone from the source too, as if it was never uploaded.
    media = src / ".git" / "lfs" / "objects"
    gone = _oid(missing)
    (media / gone[:2] / gone[2:4] / gone).unlink()

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--local", str(src), str(clone), env={"GIT_LFS_SKIP_SMUDGE": "1"})
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "test")
    # Stage everything on an orphan branch, as deploy-huggingface.sh does.
    _git(clone, "checkout", "-q", "--orphan", "huggingface-deploy")
    _git(clone, "rm", "-r", "-q", "--cached", ".")
    _git(clone, "add", "-A", env={"GIT_LFS_SKIP_SMUDGE": "1"})
    return {"src": src, "clone": clone, "kept": _oid(kept), "missing": _oid(missing)}


def test_scripts_are_valid_bash():
    for script in (HELPER, DEPLOY):
        done = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr


@needs_git_lfs
def test_staged_pointers_lists_each_lfs_file_with_its_oid(deploy_clone):
    done = _helper(deploy_clone["clone"], "lfs_staged_pointers")
    assert done.returncode == 0, done.stderr
    lines = sorted(done.stdout.splitlines())
    assert lines == sorted(
        [f"{deploy_clone['kept']} img/kept.png", f"{deploy_clone['missing']} img/missing one.png"]
    )


@needs_git_lfs
def test_fetch_then_drop_keeps_fetchable_and_drops_missing(deploy_clone):
    clone = deploy_clone["clone"]
    fetched = _helper(clone, f'lfs_fetch_staged "{deploy_clone["src"]}" main')
    assert fetched.returncode == 0, fetched.stderr

    dropped = _helper(clone, "lfs_drop_missing_staged")
    assert dropped.returncode == 0, dropped.stderr
    assert dropped.stdout.strip() == "1"
    assert "img/missing one.png" in dropped.stderr

    staged = _git(clone, "ls-files").splitlines()
    assert "img/kept.png" in staged
    assert "README.md" in staged
    assert "img/missing one.png" not in staged


@needs_git_lfs
def test_drop_without_fetch_drops_every_unfetched_pointer(deploy_clone):
    clone = deploy_clone["clone"]
    dropped = _helper(clone, "lfs_drop_missing_staged")
    assert dropped.returncode == 0, dropped.stderr
    assert dropped.stdout.strip() == "2"
    staged = _git(clone, "ls-files").splitlines()
    assert staged == [".gitattributes", "README.md"]


def test_deploy_fetches_then_drops_before_it_pushes():
    text = DEPLOY.read_text()
    assert 'lfs_objects.sh"' in text
    fetch = text.index("lfs_fetch_staged ")
    drop = text.index("lfs_drop_missing_staged")
    commit = text.index('git commit -m "Clean HuggingFace deployment')
    push = text.index('git push "$PUSH_URL"')
    assert fetch < drop < commit < push
    # The isolated clone's origin is the local checkout, so the parent passes the real one.
    assert "HF_DEPLOY_LFS_REMOTE=" in text
