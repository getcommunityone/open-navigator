"""PR conventions (AGENTS.md, "Issues first"; issue #225): every pull request belongs to a logged issue.

Fails, naming each problem, when the branch is not <type>/<issue>-<slug>, when the description has no
"Closes #<n>" (or Fixes / Refs), when the branch and the description name different issues, or when the linked
issue, opened from PARTS_SINCE, lacks one of the four parts. Tool branches (dependabot/, renovate/) and pull requests
opened before PARTS_SINCE are not checked. Run by .github/workflows/pr-conventions.yml on each pull request; reads
the event file and, with the workflow's read-only token, the linked issue."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

PARTS = ("Problem", "Done when", "Contract", "Read first")
PARTS_SINCE = "2026-11-14"
TYPES = "feat|fix|docs|chore|refactor|test|perf|ci|build|revert"
BRANCH = re.compile(rf"^(?:{TYPES})/(\d+)-[a-z0-9][a-z0-9-]{{0,39}}$")
TOOL_BRANCHES = ("dependabot/", "renovate/")
LINK = re.compile(r"\b(?:closes|closed|close|fixes|fixed|fix|resolves|resolved|resolve|refs)\s+#(\d+)\b", re.IGNORECASE)


def linked_issue_numbers(body: str) -> list[int]:
    """The issues a PR description links, in order: Closes / Fixes / Resolves / Refs #<n>."""
    return [int(n) for n in LINK.findall(body or "")]


def missing_parts(issue_body: str) -> list[str]:
    """The four parts an issue body lacks, as headings (## Problem) or bold labels (**Problem:**)."""
    out = []
    for part in PARTS:
        word = re.escape(part)
        heading = re.search(rf"^\s*#+\s*{word}\b", issue_body or "", re.IGNORECASE | re.MULTILINE)
        bold = re.search(rf"\*\*\s*{word}\s*:?\s*\*\*", issue_body or "", re.IGNORECASE)
        if not (heading or bold):
            out.append(part)
    return out


def applies_to_pr(created_at: str) -> bool:
    """Only pull requests opened from PARTS_SINCE are checked; older ones keep the rules they were opened under."""
    return (created_at or "")[:10] >= PARTS_SINCE


def check(branch: str, body: str, issue: dict | None = None) -> list[str]:
    """The problems with one pull request; an empty list means it passes."""
    if branch.startswith(TOOL_BRANCHES):
        return []
    problems = []
    m = BRANCH.match(branch)
    if not m:
        problems.append(f"branch '{branch}' is not <type>/<issue>-<slug> (e.g. fix/71-ct-county-map): open or find the "
                        "issue first and put its number in the branch name (AGENTS.md, 'Branches and pull requests')")
    links = linked_issue_numbers(body)
    if not links:
        problems.append("the PR description has no 'Closes #<issue>' (or 'Refs #<issue>' for one part of a larger issue)")
    if m and links and int(m.group(1)) not in links:
        problems.append(f"the branch names issue #{m.group(1)} but the description links "
                        + ", ".join(f"#{n}" for n in links))
    if issue is not None and (issue.get("created_at") or "")[:10] >= PARTS_SINCE:
        miss = missing_parts(issue.get("body") or "")
        if miss:
            problems.append(f"issue #{issue.get('number')} lacks: {', '.join(miss)} - add them as headings before the "
                            "first commit (AGENTS.md, 'What an issue says')")
    return problems


def fetch_issue(repo: str, number: int, token: str) -> dict | None:
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{number}",
                                 headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001 - a missing issue is reported, not a crash
        print(f"could not read issue #{number}: {e}")
        return None


def main() -> int:
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    pr = event.get("pull_request") or {}
    if not applies_to_pr(pr.get("created_at", "")):
        print(f"PR opened {pr.get('created_at', '?')[:10]}, before {PARTS_SINCE}: not checked.")
        return 0
    branch, body = (pr.get("head") or {}).get("ref", ""), pr.get("body") or ""
    m, links = BRANCH.match(branch), linked_issue_numbers(body)
    number = int(m.group(1)) if m else (links[0] if links else None)
    issue = fetch_issue(os.environ.get("GITHUB_REPOSITORY", ""), number, os.environ.get("GITHUB_TOKEN", "")) if number else None
    if number and issue is None:
        print(f"issue #{number} could not be read: open it first.")
        return 1
    problems = check(branch, body, issue)
    for p in problems:
        print(f"::error::{p}")
    print("PR conventions: OK" if not problems else f"PR conventions: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
