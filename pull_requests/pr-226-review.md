---
pr: 226
branch: docs/225-agents-issue-logging
title: "docs(agents): log every change as an issue first, and check it on each PR"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: read-only reviewer subagent + coordinator verification
verdict: approve
---

# PR Review: docs(agents): log every change as an issue first, and check it on each PR

## Summary

This PR makes issue logging part of how every agent works in the repository (issue #225, with the owner's dated
addition of the create-PR and review-PR prompts). `AGENTS.md` says an issue with Problem, Done when, Contract and Read
first comes before the first commit, follow-ups and failures become their own issues, and the branch and PR name the
issue. `CLAUDE.md` imports it, the `PR conventions` workflow checks it, and `/create-pr`, `/pr-review` and a shared
rubric write each review to `pull_requests/`. The first review pass (on `dc935c3`) found one important defect and six
minor ones. All seven are fixed in the commit that adds this file, with tests. The verdict is approve.

## Scope of Change

- Files changed: 14 (+~640 / -7), no generated files
- Areas touched: agents (AGENTS.md, CLAUDE.md, .claude/), ci (.github/), tests
- Commits:
  - f79c12e docs(agents): log every change as an issue first, and check it on each PR
  - dc935c3 feat(agents): add /create-pr and /pr-review prompts, a review rubric, and pull_requests/ for reviews
  - (this commit) fix(ci): skip tool branches before any lookup, accept "Closes:", require text in each part
- Range reviewed: `6fa4943..dc935c3`, then the fix commit

## CI Status

| Check | Status (on dc935c3) |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success (the new check, on its own PR) |
| Docker Build Test | skipped (no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. The only token is `${{ secrets.GITHUB_TOKEN }}`, read from the environment with read-only
  permissions.
- **Fabricated data in a served path:** clean. Nothing in `api/` or `web_app/src/` changes. The numbers in the tests
  are fixtures for the CI script.
- **Personal data:** clean.
- **Destructive data changes:** clean. The only deletion is `pull_request/README.md`, which moves to `pull_requests/`.

## Strengths

- The check passes on pull requests opened before November 14, 2026, so the PRs already open aren't turned red, and
  it isn't made a required check without the owner.
- The workflow uses the `pull_request` trigger with read-only `pull-requests` and `issues` permissions, and never puts
  event text into a shell command.
- The `.gitignore` change (`.claude/*` plus negations) works: only `.claude/settings.local.json` stays ignored (checked
  with `git check-ignore -v`).
- The prompts, the rubric and `AGENTS.md` agree on the four scans, the four required checks, the review path and the
  branch format.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking): fixed

1. `.github/scripts/pr_conventions.py`, `main()`: **a Dependabot or Renovate PR could fail the check.** The tool-branch
   skip lived only in `check()`, but `main()` first looked up any `Fixes #n` in the PR body. Those bodies quote upstream
   changelogs, so the lookup of an upstream issue number failed and exited 1. Verified by running `main()` on a stubbed
   event (`dependabot/npm_and_yarn/vite-5`, body "- Fixes #4521 upstream"), which exited 1. **Fixed:** `main()` returns
   0 for tool branches before any lookup. Covered by `test_main_skips_tool_branches_even_when_the_body_quotes_upstream_fixes`.

### 🔵 Nits / suggestions (Minor): fixed

2. `LINK` didn't accept the colon form (`Closes: #7`), which GitHub honours. **Fixed** (`\s*:?\s*#`), with
   `test_the_colon_form_counts_as_a_link`.
3. An issue made from the template and left unfilled passed the four-parts check, because the headings were there.
   **Fixed:** a part now needs text under it, outside HTML comments and code fences. The template's guidance moved into
   comments, so an unfilled template lacks all four parts. Covered by `test_an_unfilled_template_lacks_all_four_parts`
   and `test_headings_inside_comments_or_with_no_text_do_not_count`.
4. The test of `CLAUDE.md`'s root rule sliced to the end of the file, so any later mention of `AGENTS.md` passed.
   **Fixed:** it reads the Root bullet itself.
5. An unreadable issue exited 1 with a plain message that wasn't annotated on the PR, and called every failure "open
   it first". **Fixed:** `::error::` annotations; 404 says the issue doesn't exist; other errors are retried once and
   named. Covered by `test_main_fails_with_an_annotation_when_the_linked_issue_cannot_be_read`.
6. The check doesn't re-run when the linked issue is edited. **Documented** in `AGENTS.md`: re-run it from the PR's
   Checks tab after fixing the issue.
7. `/create-pr`'s body template offered only `Closes #<issue>`. **Fixed:** one line on when to use `Refs #<issue>`.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | Branch `docs/225-agents-issue-logging`; description says `Closes #225`; issue #225 has the four parts and a dated update for the added scope |
| Conventional Commits | Pass | `docs(agents)`, `feat(agents)`, `fix(ci)`, each with the co-author trailer |
| No fabricated data | Pass | Scan clean |
| New Python in `packages/` | N/A | A CI script under `.github/scripts/` and a test; nothing in `scripts/` |
| dbt for transformations | N/A | |
| Naming, keys, calendar years | N/A | No data models |
| Scope label, match evidence | N/A | No UI |
| Docs | Pass | `AGENTS.md` is on the updated root allow-list; decisions point to `web_docs/docs/development/` |
| Telemetry and logging | N/A | A CI script prints GitHub annotations |
| Tests | Pass | 24 tests in `tests/test_pr_conventions.py`, written before the code they cover (the first 16 and the 6 for the review findings each failed first) |
| Shared libraries | N/A | No `packages/` change |

## Test Coverage

`tests/test_pr_conventions.py` covers each rule: the branch format, the links (including `Refs`, `Fixes` and the
colon form), the branch and description naming the same issue, each missing part, bold-label parts, an unfilled
template, headings inside comments, the date cut-offs, tool branches in `check()` and in `main()`, the unreadable-issue
annotation, the workflow's permissions, and the rule text in `AGENTS.md`, `CLAUDE.md`, the prompts and the template.
Run locally: `pytest -q tests/test_pr_conventions.py` gives 24 passed. The script was also run end to end on this PR's
own event and issue (`PR conventions: OK`).

## Verdict

Approve. The important finding (tool branches) and the six minor ones are fixed with tests. Before making `PR
conventions` a required check, let one Dependabot PR run through it.
