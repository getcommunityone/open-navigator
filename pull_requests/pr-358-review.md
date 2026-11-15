---
pr: 358
branch: docs/357-gpu-colab-only
title: "docs(agents): GPU runs use the owner's Colab only, and a paid run needs the owner's yes"
author: claude
reviewed_at: 2026-11-15
reviewer: coordinator, against .claude/review-rubric.md
verdict: approve
---

# PR Review: docs(agents): GPU runs use the owner's Colab only, and a paid run needs the owner's yes

## Summary
Closes #357. Adds a "GPU and paid compute" section to `AGENTS.md` and a decision page under
`web_docs/docs/development/`, as the owner decided on November 15. No code, data or UI changes. No Critical or
Important findings.

## Scope of Change
- Files changed: 3 (`AGENTS.md`, `web_docs/docs/development/gpu-compute-decisions.md`, `tests/test_gpu_rules.py`)
- Commit: d92b8e8 docs(agents): send GPU runs to the owner's Colab only, with the owner's yes

## Checks
| Check | Result |
|---|---|
| Issue #357 has the four parts and a label before the first commit; branch `docs/357-...`; `Closes #357` | yes |
| Test first: `tests/test_gpu_rules.py` failed, then passed; with the PR-conventions tests, 25 passed | yes |
| Docs rules (CLAUDE.md): page under `web_docs/docs/`, kebab-case, lowercase, YAML frontmatter | yes |
| Decisions written down in a page and linked from the rule (AGENTS.md) | yes |
| No fabricated data: the 60 and 17.73 hours come from health-transformation-lab-nlp's quota reading (its ADR 0007) | yes |
| Conventional Commit message | yes |

## Findings
### Minor
1. The rule names health-transformation-lab-nlp's ADR 0007, which is in an open PR there (798); the page's reasons
   stand without it.

## Verdict
Approve. Merge when the required checks are green; it changes the agent rules, so on the owner's word.
