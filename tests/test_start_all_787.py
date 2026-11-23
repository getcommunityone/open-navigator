"""#787: start-all.sh clears its ports, starts unattended, and fails loudly if a service is down.

Runs a copy of the script against fake services (tiny Python web servers) on free ports, in the
no-tmux mode, so it needs no real API, Node or tmux.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "start-all.sh"

pytestmark = pytest.mark.skipif(
    not all(shutil.which(c) for c in ("bash", "curl", "lsof")),
    reason="needs bash, curl and lsof",
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


FAKE_MAIN = """
import http.server, os, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"api")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(("127.0.0.1", int(os.environ["START_ALL_API_PORT"])), H).serve_forever()
"""

FAKE_NPM = """#!/bin/bash
# fake npm: `run dev` is the web app, `start` is the docs site
if [ "$2" = "dev" ]; then
  [ -n "$FAKE_WEB_FAIL" ] && { echo "vite: cannot find module x"; exit 1; }
  exec {py} -m http.server "$START_ALL_WEB_PORT" --bind 127.0.0.1
else
  exec {py} -m http.server "$START_ALL_DOCS_PORT" --bind 127.0.0.1
fi
"""


@pytest.fixture()
def sandbox(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "activate").write_text("")
    (repo / "web_app" / "node_modules").mkdir(parents=True)
    (repo / "web_docs" / "node_modules").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "start-all.sh")
    (repo / "main.py").write_text(FAKE_MAIN)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    py = sys.executable
    (bin_dir / "python").write_text(f'#!/bin/bash\nexec {py} "$@"\n')
    (bin_dir / "npm").write_text(FAKE_NPM.replace("{py}", py))
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    ports = {"API": _free_port(), "WEB": _free_port(), "DOCS": _free_port()}
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "START_ALL_NO_TMUX": "1",
        "START_ALL_WAIT_SECONDS": "10",
        **{f"START_ALL_{k}_PORT": str(v) for k, v in ports.items()},
    }
    yield repo, env, ports
    for pidfile in (repo / "logs").glob("*.pid") if (repo / "logs").exists() else []:
        try:
            os.kill(int(pidfile.read_text().strip()), signal.SIGKILL)
        except (OSError, ValueError):
            pass


def _run(repo, env, *args, timeout=60):
    return subprocess.run(
        ["bash", "start-all.sh", *args],
        cwd=repo,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _status(port: int) -> str:
    out = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-m", "2", "-w", "%{http_code}", f"http://127.0.0.1:{port}/"],
        capture_output=True,
        text=True,
    )
    return out.stdout


def test_starts_everything_unattended_and_reports_ok(sandbox):
    repo, env, ports = sandbox
    done = _run(repo, env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "OK" in done.stdout and "FAILED" not in done.stdout
    assert _status(ports["API"]) == "200"
    assert _status(ports["WEB"]) == "200"
    assert _status(ports["DOCS"]) == "200"


def test_clears_a_stale_process_holding_a_port(sandbox):
    repo, env, ports = sandbox
    stale = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(ports["WEB"]), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1)
        assert _status(ports["WEB"]) == "200"
        done = _run(repo, env)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "is in use" in done.stdout
        assert stale.wait(timeout=10) is not None  # the stale process was stopped
        assert _status(ports["WEB"]) == "200"  # and a new one answers
    finally:
        stale.kill()


def test_a_dead_web_app_fails_loudly_with_its_log(sandbox):
    repo, env, _ = sandbox
    env["FAKE_WEB_FAIL"] = "1"
    env["START_ALL_WAIT_SECONDS"] = "4"
    done = _run(repo, env)
    assert done.returncode != 0
    assert "FAILED" in done.stdout and "Web app" in done.stdout
    assert "cannot find module x" in done.stdout  # the log lines are shown


def test_no_docs_flag_skips_docs(sandbox):
    repo, env, ports = sandbox
    done = _run(repo, env, "--no-docs")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _status(ports["DOCS"]) != "200"


def test_running_twice_replaces_the_first_copy(sandbox):
    repo, env, ports = sandbox
    assert _run(repo, env).returncode == 0
    first = int((repo / "logs" / "api.pid").read_text().strip())
    assert _run(repo, env).returncode == 0
    second = int((repo / "logs" / "api.pid").read_text().strip())
    assert first != second
    with pytest.raises(OSError):
        os.kill(first, 0)  # the old API is gone
    assert _status(ports["API"]) == "200"


def test_vite_refuses_to_hop_ports():
    cfg = (ROOT / "web_app" / "vite.config.ts").read_text(encoding="utf-8")
    assert "strictPort: true" in cfg
