---
pr: 255
branch: docs/254-epic-story-attributes
title: "docs(agents): issues and pull requests for planned work link their epic and user story"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review)
verdict: approve
---

# PR Review: docs(agents): issues and pull requests for planned work link their epic and user story

## Summary

This PR writes down the owner's PI4 rule: planned work opens with an Attributes table that links its Epic and User
story as markdown links, and its pull request repeats the table. It changes three files: `AGENTS.md` ("What an
issue says"), the work-item issue template, and `/create-pr`. It's docs and prompts only, and the PR conventions
tests still pass. The verdict is approve.

## Scope of Change

- Files changed: 3 (+22 / -1), plus this review
- Areas touched: agents (`AGENTS.md`, `.claude/commands/`), `.github/ISSUE_TEMPLATE/`
- Commits: e6a9ef4 docs(agents): issues and pull requests for planned work link their epic and user story

## CI Status

Checked green on the head before merging (Frontend Build, Documentation Build, Backend Tests, API Types).
`pytest tests/test_pr_conventions.py`: 24 passed locally.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. The template's placeholders (`<key>`, `<epic>`) are guidance in an
  issue template, not served data.
- **Personal data:** clean.
- **Destructive data changes:** none.

## Strengths

- The rule points at real examples (#235, #242, #253), so an agent can copy the format instead of guessing.
- The template puts the table above the four parts, so the PR conventions check, which looks for the four headings,
  still passes.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **Nothing enforces the table.** That's deliberate (see "Not in this PR"). If links start going missing, the
   conventions check could require an `Epic` row whenever the linked issue is a sub-issue of an epic.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| Issue first, four parts | ✅ #254 |
| Branch `<type>/<issue>-<slug>`, `Closes #<issue>` | ✅ `docs/254-epic-story-attributes`, `Closes #254` |
| Changes to the rules go by PR | ✅ |
| Conventional Commits | ✅ |

## Test Coverage

No code changes. The PR conventions tests (24) pass with the new template.

## Verdict

**Approve.** Merge when the four required checks are green.
