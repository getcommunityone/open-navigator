"""Write ``pull_requests/pr-<n>-review.md`` for a PR when missing or stale (#648).

Runs the rubric's mandatory scans as heuristics (no model required). When
``GEMINI_API_KEY`` / ``GOOGLE_API_KEY`` is set, optionally asks Flash-Lite for a
short summary; scan verdicts still govern blocking.

Loop guard: callers skip when the only changed files are under ``pull_requests/``
or the commit message contains ``[skip review]``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

VALID_VERDICTS = ("approve", "approve-with-nits", "request-changes")
VERDICT_RE = re.compile(
    r"^verdict:\s*(approve|approve-with-nits|request-changes)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Cheap secret-shaped tokens in the diff (same spirit as the rubric scan).
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"(?i)postgres(ql)?://[^:\s]+:[^@\s]+@"),
    re.compile(r"(?i)AIza[0-9A-Za-z_\-]{30,}"),  # Google API key shape
]


def review_path(repo_root: Path, pr_number: int) -> Path:
    return repo_root / "pull_requests" / f"pr-{pr_number}-review.md"


def has_valid_verdict(text: str) -> bool:
    return bool(VERDICT_RE.search(text or ""))


def parse_verdict(text: str) -> str | None:
    m = VERDICT_RE.search(text or "")
    return m.group(1).lower() if m else None


def git_diff(repo_root: Path, base: str, head: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--no-color", f"{base}...{head}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
    except subprocess.CalledProcessError:
        out = subprocess.check_output(
            ["git", "diff", "--no-color", base, head],
            cwd=repo_root,
            text=True,
            errors="replace",
        )
    return out


def git_changed_files(repo_root: Path, base: str, head: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
    except subprocess.CalledProcessError:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", base, head],
            cwd=repo_root,
            text=True,
            errors="replace",
        )
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def scan_diff(diff: str) -> list[str]:
    """Return blocking findings from heuristic scans."""
    findings: list[str] = []
    # Only added lines
    added = "\n".join(
        ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    )
    for pat in _SECRET_PATTERNS:
        if pat.search(added):
            findings.append(f"Possible secret or credential pattern matched: `{pat.pattern[:48]}…`")
            break
    # Fabricated-looking dollar amounts in served paths (heuristic, advisory→blocking only if huge)
    if re.search(r"(?i)(budget|contribution|donation).{0,40}\$\s*[\d,]{4,}", added):
        if re.search(r"(?m)^\+.*(api/|web_app/src/)", diff) or "api/" in diff or "web_app/src/" in diff:
            # Only flag if the dollar amount is on an added line in those trees — checked via file list by caller
            pass
    return findings


def scan_served_fabrication(diff: str, files: list[str]) -> list[str]:
    served = [f for f in files if f.startswith("api/") or f.startswith("web_app/src/")]
    if not served:
        return []
    # Hard-coded money in non-test served code
    findings = []
    money = re.compile(r"""(?i)(['"])\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?\1|amount\s*=\s*\d{4,}""")
    for ln in diff.splitlines():
        if not ln.startswith("+") or ln.startswith("+++"):
            continue
        if "/test" in ln or ".test." in ln or "fixtures" in ln:
            continue
        if money.search(ln) and ("budget" in ln.lower() or "dollar" in ln.lower() or "amount" in ln.lower()):
            findings.append("Possible hard-coded financial figure in a served path (No Fabricated Data).")
            break
    return findings


def only_review_files(files: list[str]) -> bool:
    return bool(files) and all(
        f.startswith("pull_requests/") and f.endswith("-review.md") for f in files
    )


def build_review(
    *,
    pr_number: int,
    title: str,
    branch: str,
    author: str,
    files: list[str],
    blocking: list[str],
    head_sha: str,
) -> str:
    if blocking:
        verdict = "request-changes"
    elif len(files) > 40:
        verdict = "approve-with-nits"
    else:
        verdict = "approve"

    today = date.today().isoformat()
    strengths = (
        "- Automated scans found no secret/credential patterns in added lines."
        if not blocking
        else "- (blocked on scan findings below)"
    )
    blocking_md = (
        "\n".join(f"- {b}" for b in blocking) if blocking else "None."
    )
    files_md = "\n".join(f"- `{f}`" for f in files[:40]) or "- (no file list)"
    if len(files) > 40:
        files_md += f"\n- …and {len(files) - 40} more"

    return f"""---
pr: {pr_number}
branch: {branch}
title: {json.dumps(title)}
author: {author}
reviewed_at: {today}
reviewer: github-actions
head_sha: {head_sha}
verdict: {verdict}
---

# PR Review: {title}

## Summary

Automated review (#648) for PR #{pr_number} on `{branch}`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

{files_md}

## CI Status

See the PR checks on `{head_sha[:12]}`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: {"**findings**" if any("secret" in b.lower() or "credential" in b.lower() for b in blocking) else "clean (heuristic)"}
- Fabricated data / personal / destructive: see findings

## Strengths

{strengths}

## Findings

### 🔴 Blocking (Critical)

{blocking_md}

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**{verdict}**
"""


def maybe_llm_summary(diff: str, title: str) -> str:
    """Optional one-paragraph summary; never overrides scan verdicts."""
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key or len(diff) > 120_000:
        return ""
    # Keep dependency-free: skip model call unless google-genai is importable.
    try:
        from google import genai  # type: ignore
    except Exception:
        return ""
    try:
        client = genai.Client(api_key=key)
        prompt = (
            "In 3 short bullets, summarize what this PR changes and any risk. "
            f"Title: {title}\n\nDiff (truncated):\n{diff[:40_000]}"
        )
        resp = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        text = (getattr(resp, "text", None) or "").strip()
        return text[:1500]
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::LLM summary skipped: {exc}")
        return ""


def write_review_file(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--base", default="origin/main")
    p.add_argument("--head", default="HEAD")
    p.add_argument("--title", default="")
    p.add_argument("--branch", default="")
    p.add_argument("--author", default="unknown")
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument(
        "--force",
        action="store_true",
        help="Rewrite even when a valid verdict already exists",
    )
    args = p.parse_args()
    root = args.repo_root.resolve()
    path = review_path(root, args.pr)

    files = git_changed_files(root, args.base, args.head)
    if only_review_files(files) and not args.force:
        print("Only review files changed — skip auto-review (loop guard).")
        return 0

    if path.is_file() and has_valid_verdict(path.read_text(encoding="utf-8")) and not args.force:
        # Refresh if head_sha in frontmatter is stale? Keep agent-written reviews.
        existing = path.read_text(encoding="utf-8")
        if "reviewer: github-actions" not in existing:
            print(f"{path} already has a non-bot review — leave it.")
            return 0
        m = re.search(r"^head_sha:\s*(\S+)", existing, re.MULTILINE)
        head_full = subprocess.check_output(
            ["git", "rev-parse", args.head], cwd=root, text=True
        ).strip()
        if m and m.group(1) == head_full:
            print(f"{path} already covers {head_full[:12]}")
            return 0

    diff = git_diff(root, args.base, args.head)
    blocking = scan_diff(diff) + scan_served_fabrication(diff, files)
    head_sha = subprocess.check_output(
        ["git", "rev-parse", args.head], cwd=root, text=True
    ).strip()
    title = args.title or f"PR #{args.pr}"
    body = build_review(
        pr_number=args.pr,
        title=title,
        branch=args.branch or "unknown",
        author=args.author,
        files=files,
        blocking=blocking,
        head_sha=head_sha,
    )
    summary = maybe_llm_summary(diff, title)
    if summary:
        body = body.replace(
            "## Summary\n\n",
            f"## Summary\n\n{summary}\n\n",
            1,
        )
    write_review_file(path, body)
    print(f"Wrote {path} verdict={parse_verdict(body)}")
    # Emit path for the workflow
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"review_path={path.relative_to(root)}\n")
            fh.write("wrote=true\n")
            fh.write(f"verdict={parse_verdict(body)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
