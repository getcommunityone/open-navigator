"""Automated writer for pull_requests/pr-<n>-review.md (#648)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "auto_pr_review.py"


@pytest.fixture(scope="module")
def apr():
    spec = importlib.util.spec_from_file_location("auto_pr_review", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_review_approve_when_clean(apr):
    body = apr.build_review(
        pr_number=1,
        title="ci(test): example",
        branch="ci/648-pr-review-auto",
        author="bot",
        files=[".github/scripts/auto_pr_review.py"],
        blocking=[],
        head_sha="abc123" * 6 + "abcd",
    )
    assert "verdict: approve" in body
    assert apr.has_valid_verdict(body)
    assert apr.parse_verdict(body) == "approve"


def test_build_review_request_changes_on_blocking(apr):
    body = apr.build_review(
        pr_number=2,
        title="bad",
        branch="feat/1-x",
        author="x",
        files=["api/main.py"],
        blocking=["Possible secret or credential pattern matched: `x`"],
        head_sha="deadbeef" * 5,
    )
    assert apr.parse_verdict(body) == "request-changes"


def test_scan_diff_finds_credential_shaped_token(apr):
    # Shape matches auto_pr_review._SECRET_PATTERNS without a PEM block (pre-commit).
    fake = "api_key=" + ("x" * 24)
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n+++ b/x.py\n"
        "@@ -0,0 +1 @@\n"
        f"+{fake}\n"
    )
    assert apr.scan_diff(diff)


def test_only_review_files_loop_guard(apr):
    assert apr.only_review_files(["pull_requests/pr-9-review.md"]) is True
    assert apr.only_review_files(["pull_requests/pr-9-review.md", "api/main.py"]) is False
    assert apr.only_review_files([]) is False


def test_main_leaves_non_bot_review_alone(apr, tmp_path, monkeypatch):
    (tmp_path / "pull_requests").mkdir()
    path = tmp_path / "pull_requests" / "pr-7-review.md"
    original = "---\nverdict: approve\nreviewer: human\n---\n# ok\n"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(apr, "git_changed_files", lambda *a, **k: ["api/x.py"])
    monkeypatch.setattr(
        "sys.argv",
        ["auto_pr_review.py", "--pr", "7", "--repo-root", str(tmp_path), "--title", "t"],
    )
    assert apr.main() == 0
    assert path.read_text(encoding="utf-8") == original


# A title that broke the job on #893 and one that tries to run commands (#895).
HOSTILE_TITLES = [
    'fix(web_app): turn it into "Explore [measure] in [place]" that fits one screen',
    "it's `touch {marker}` and $(touch {marker}) and ${{HOME}} and \"; touch {marker}; echo \"",
    "--force",
]


@pytest.mark.parametrize("raw", HOSTILE_TITLES)
def test_main_writes_the_title_as_given(apr, tmp_path, monkeypatch, raw):
    import json

    title = raw.format(marker=tmp_path / "pwned")
    monkeypatch.setattr(apr, "git_changed_files", lambda *a, **k: ["api/x.py"])
    monkeypatch.setattr(apr, "git_diff", lambda *a, **k: "")
    monkeypatch.setattr(apr.subprocess, "check_output", lambda *a, **k: "abc123\n")
    # The workflow passes --title=VALUE so a title that starts with "-" stays a value.
    monkeypatch.setattr(
        "sys.argv",
        ["auto_pr_review.py", "--pr", "7", "--repo-root", str(tmp_path),
         f"--title={title}", "--branch=fix/895-x", "--author=someone"],
    )
    assert apr.main() == 0
    text = (tmp_path / "pull_requests" / "pr-7-review.md").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("title: "))
    assert json.loads(line[len("title: "):]) == title
    assert f"# PR Review: {title}\n" in text
    assert not (tmp_path / "pwned").exists()


UNTRUSTED = ("github.event.pull_request.title", "github.event.pull_request.body", "github.head_ref",
             "github.base_ref", "github.event.pull_request.user.login", "github.event.pull_request.head.ref")


def _auto_review_steps():
    import yaml

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "pr-conventions.yml").read_text(encoding="utf-8"))
    return wf["jobs"]["auto-review"]["steps"]


def test_no_run_block_expands_pr_fields_into_the_shell():
    # ${{ }} is pasted into the script before bash reads it, so a quote in a title ends the argument (#895).
    for step in _auto_review_steps():
        for field in UNTRUSTED:
            assert field not in step.get("run", ""), f"{step.get('name')}: {field} inside run:"


@pytest.mark.parametrize("raw", HOSTILE_TITLES)
def test_review_step_runs_with_a_hostile_title_and_executes_none_of_it(tmp_path, raw):
    import os
    import re
    import shutil
    import subprocess
    import sys

    step = next(s for s in _auto_review_steps() if s.get("name") == "Write review if missing or stale")
    marker = tmp_path / "pwned"
    title = raw.format(marker=marker)
    repo = tmp_path / "repo"
    (repo / ".github" / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / ".github" / "scripts" / "auto_pr_review.py")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo)]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    subprocess.run([*git, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "change"], check=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "python").symlink_to(sys.executable)
    # The values GitHub would put in the step's env: block for this pull request.
    fake = {
        "github.event.pull_request.number": "7",
        "github.base_ref": "main",
        "github.event.pull_request.title": title,
        "github.head_ref": "fix/895-pr-title-env",
        "github.event.pull_request.user.login": "someone",
    }
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}
    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)
    expand = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
    for name, value in (step.get("env") or {}).items():
        expr = expand.fullmatch(str(value))
        if expr and expr.group(1) in fake:
            env[name] = fake[expr.group(1)]
    # Expand ${{ }} in run: the way Actions does, by pasting the text in before bash parses it.
    script = expand.sub(lambda m: fake[m.group(1)], step["run"])
    proc = subprocess.run(["bash", "-e", "-c", script], cwd=repo, env=env, capture_output=True, text=True, check=False)
    assert not marker.exists(), "part of the title ran as a command"
    assert proc.returncode == 0, proc.stderr
    text = (repo / "pull_requests" / "pr-7-review.md").read_text(encoding="utf-8")
    assert f"# PR Review: {title}\n" in text
    assert "branch: fix/895-pr-title-env" in text and "author: someone" in text
