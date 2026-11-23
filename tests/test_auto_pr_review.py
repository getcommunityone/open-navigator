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
