"""The Space start-up script that swaps served Git LFS pointers for the real files (#911).

The image is built from a context that holds LFS files as pointers, so the web build served
130-byte pointer text for the strategic plan PDF and the logos. The script downloads each
object from the Space's repository and accepts it only when its SHA-256 equals the pointer's oid.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".huggingface" / "restore_lfs_static.sh"


def _pointer(content: bytes) -> bytes:
    oid = hashlib.sha256(content).hexdigest()
    return f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(content)}\n".encode()


@pytest.fixture()
def served(tmp_path):
    """A file server standing in for the Space repository's resolve/main address."""
    remote = tmp_path / "remote"
    remote.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(remote))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield remote, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run(repo: Path, static: Path, base: str | None) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin"}
    if base:
        env["LFS_RESOLVE_BASE"] = base
    return subprocess.run(["bash", str(SCRIPT), str(repo), str(static)], env=env, capture_output=True, text=True)


def _layout(tmp_path: Path, real: bytes) -> tuple[Path, Path, Path]:
    repo, static = tmp_path / "repo", tmp_path / "static"
    (repo / "web_app/public/pdf").mkdir(parents=True)
    (repo / "web_app/public/pdf/plan.pdf").write_bytes(_pointer(real))
    (static / "pdf").mkdir(parents=True)
    target = static / "pdf/plan.pdf"
    target.write_bytes(_pointer(real))
    (static / "index.html").write_text("<html></html>")
    return repo, static, target


def test_a_pointer_is_replaced_by_its_object_when_the_hash_matches(tmp_path, served):
    remote, base = served
    real = b"%PDF-1.7 the real file " * 50
    repo, static, target = _layout(tmp_path, real)
    (remote / "web_app/public/pdf").mkdir(parents=True)
    (remote / "web_app/public/pdf/plan.pdf").write_bytes(real)

    out = _run(repo, static, base)

    assert out.returncode == 0, out.stderr
    assert target.read_bytes() == real
    assert "restored 1 file(s), 0 not restored" in out.stdout
    assert (static / "index.html").read_text() == "<html></html>"


def test_a_download_with_the_wrong_content_is_rejected_and_the_start_still_succeeds(tmp_path, served):
    remote, base = served
    real = b"%PDF-1.7 the real file " * 50
    repo, static, target = _layout(tmp_path, real)
    (remote / "web_app/public/pdf").mkdir(parents=True)
    (remote / "web_app/public/pdf/plan.pdf").write_bytes(b"something else entirely")

    out = _run(repo, static, base)

    assert out.returncode == 0
    assert target.read_bytes() == _pointer(real)
    assert "restored 0 file(s), 1 not restored" in out.stdout
    assert not list(static.rglob("*.lfs-tmp"))


def test_a_missing_object_leaves_the_pointer_and_does_not_fail(tmp_path, served):
    _, base = served
    real = b"x" * 2000
    repo, static, target = _layout(tmp_path, real)

    out = _run(repo, static, base)

    assert out.returncode == 0
    assert target.read_bytes() == _pointer(real)
    assert "1 not restored" in out.stdout


def test_without_a_space_id_or_base_it_does_nothing(tmp_path):
    real = b"y" * 2000
    repo, static, target = _layout(tmp_path, real)

    out = _run(repo, static, None)

    assert out.returncode == 0
    assert "nothing to do" in out.stdout
    assert target.read_bytes() == _pointer(real)


def test_the_image_copies_the_script_and_the_start_script_calls_it():
    assert "restore_lfs_static.sh" in (ROOT / "Dockerfile.huggingface").read_text()
    assert "/app/restore_lfs_static.sh /app /app/static/frontend /app/static/docs /app/api/static" in (
        ROOT / ".huggingface" / "start.sh"
    ).read_text()
