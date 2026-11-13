"""Every change starts from a logged issue (AGENTS.md, issue #225): the PR check and the files that state the rule."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "pr_conventions.py"
PARTS = ("Problem", "Done when", "Contract", "Read first")


@pytest.fixture(scope="module")
def pc():
    spec = importlib.util.spec_from_file_location("pr_conventions", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def issue(body, created="2026-11-20T10:00:00Z", number=300):
    return {"number": number, "body": body, "created_at": created}


FULL = "## Problem\nx\n## Done when\n- y\n## Contract\n- z\n## Read first\n- w\n"


def test_a_pr_that_follows_the_rules_passes(pc):
    assert pc.check("feat/300-money-sankey", "Closes #300", issue(FULL)) == []


def test_branch_without_an_issue_number_fails_and_says_why(pc):
    problems = pc.check("feat/money-sankey", "Closes #300", issue(FULL))
    assert problems and "<type>/<issue>-<slug>" in problems[0]


def test_description_without_closes_or_refs_fails(pc):
    problems = pc.check("feat/300-money-sankey", "Adds the sankey.", issue(FULL))
    assert any("Closes #" in p for p in problems)


def test_refs_and_fixes_count_as_links(pc):
    assert pc.linked_issue_numbers("Fixes #12, refs #34 and closes #56") == [12, 34, 56]
    assert pc.check("fix/34-ct-map", "Refs #34", issue(FULL, number=34)) == []


def test_branch_and_description_must_name_the_same_issue(pc):
    problems = pc.check("feat/300-money-sankey", "Closes #301", issue(FULL))
    assert any("#300" in p and "#301" in p for p in problems)


@pytest.mark.parametrize("missing", PARTS)
def test_an_issue_missing_a_part_fails_naming_it(pc, missing):
    body = "".join(f"## {p}\ntext\n" for p in PARTS if p != missing)
    problems = pc.check("feat/300-money-sankey", "Closes #300", issue(body))
    assert any(missing in p for p in problems)


def test_bold_labels_count_as_parts(pc):
    body = "**Problem:** x\n**Done when:** y\n**Contract:** z\n**Read first:** w\n"
    assert pc.missing_parts(body) == []


def test_issues_opened_before_the_rule_pass_without_the_parts(pc):
    assert pc.check("fix/71-ct-map", "Closes #71", issue("old text", created="2026-06-04T20:47:29Z", number=71)) == []


def test_tool_branches_pass(pc):
    assert pc.check("dependabot/npm_and_yarn/vite-5.4.2", "", None) == []
    assert pc.check("renovate/loguru", "", None) == []


def test_prs_opened_before_the_rule_are_not_checked(pc):
    assert pc.applies_to_pr("2026-11-08T02:29:35Z") is False
    assert pc.applies_to_pr("2026-11-14T00:00:01Z") is True


def test_the_workflow_runs_the_check_with_read_only_issue_access():
    wf = (ROOT / ".github" / "workflows" / "pr-conventions.yml").read_text(encoding="utf-8")
    assert "pr_conventions.py" in wf and "issues: read" in wf and "pull-requests: read" in wf
    assert "contents: write" not in wf


def test_agents_md_states_the_rule_and_claude_md_imports_it():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for part in PARTS:
        assert part in agents
    assert "<type>/<issue>-<slug>" in agents and "Closes #" in agents and "action-item" in agents
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in claude.split("\n## ")[0]          # imported before the first section
    assert "AGENTS.md" in claude[claude.index("## Documentation Rules"):]   # allowed in the root


def test_the_issue_template_offers_the_four_parts():
    tpl = (ROOT / ".github" / "ISSUE_TEMPLATE" / "work-item.md").read_text(encoding="utf-8")
    for part in PARTS:
        assert f"## {part}" in tpl


def test_the_create_pr_and_pr_review_prompts_and_the_rubric_exist_and_agree():
    create = (ROOT / ".claude" / "commands" / "create-pr.md").read_text(encoding="utf-8")
    review = (ROOT / ".claude" / "commands" / "pr-review.md").read_text(encoding="utf-8")
    rubric = (ROOT / ".claude" / "review-rubric.md").read_text(encoding="utf-8")
    for text in (create, review):
        assert text.startswith("---\ndescription:")             # slash-command frontmatter
        assert "pull_requests/pr-<n>-review.md" in text and "review-rubric.md" in text
    assert "Closes #<issue>" in create and "<type>/<issue>-<slug>" in create
    for scan in ("Secrets", "Fabricated data", "Personal data", "Destructive"):
        assert scan in rubric
    for check in ("Frontend Build", "Documentation Build", "Backend Tests", "API Types"):
        assert check in rubric and check in create


def test_reviews_live_in_pull_requests_and_agents_md_says_so():
    assert (ROOT / "pull_requests" / "README.md").is_file()
    assert not (ROOT / "pull_request").exists()
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "/create-pr" in agents and "/pr-review" in agents and "pull_requests/pr-<n>-review.md" in agents
