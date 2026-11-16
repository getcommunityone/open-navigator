---
pr: 436
branch: docs/425-context-engineering
title: "docs(agents): add the context engineering principles and where each applies"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review in a fresh worktree; each finding traced in the code)
verdict: approve-with-nits
---

# PR Review: docs(agents): add the context engineering principles and where each applies

## Summary
Adds `web_docs/docs/development/context-engineering.md` (six principles, each mapped to the code that applies it and
to its gaps, plus a checklist) and a short "Context for models and agents" section in `AGENTS.md` linking it. Every
file path, docs link and code claim on the page was checked against the tree: all exist and match (for example
`CONTEXT_LABELS` in `llm/usage/calls.py`, `highlightSnippet` in `web_app/src/lib/highlight.tsx`, the ~35 KB prompt).
One reference was wrong, a branch name that doesn't exist on origin, and it is fixed on the branch. Approve with nits.

## Scope of Change
- Files changed: 2 (+223 / -0)
- Areas touched: web_docs / agents
- Commits:
  - b7b568e7 docs(agents): add the context engineering principles and where each applies
  - 3c357a2a docs(agents): name the Jev screening branch as it is on origin (review fix)
- Range reviewed: `fb865cc2..b7b568e7`, then the fix

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker changes) |

CI was read on b7b568e7; the fix commit triggers a new run.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean (docs only; the row counts quoted, 7,108 and 6,407, are dated findings
  from the linked issues).
- Personal data: clean.
- Destructive or bulky data changes: clean.

## Strengths
- Each principle names real files and an honest list of gaps, and the gaps became issues #426, #427 and #428.
- The checklist gives a reviewer something concrete to ask of a new model call.
- The `AGENTS.md` section is short and agrees with `CLAUDE.md` (read `public`, never `bronze` or `gold`).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **Fixed (3c357a2a).** `web_docs/docs/development/context-engineering.md:47` named the Jev work as branch
   `feat/jev-transcript-screening`. `git ls-remote --heads origin feat/jev-transcript-screening` returns nothing; the
   work is PR #435 on `feat/424-jev-transcript-screening`. Now names both.
2. **Left.** The "Gaps" sections describe the state on November 16, 2026; once #426, #427 and #428 merge, the
   principle 2, 4 and 5 gaps will read as still open. Worth linking those issues from the gaps, or updating the page
   when they land.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `docs/425-context-engineering`; `Closes #425`; the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | Described accurately |
| Docs | Yes | Under `web_docs/docs/development/`, kebab-case, frontmatter; no new root `.md` |
| Telemetry and logging | n/a | |
| Tests | n/a | Docs only; the docs build is the check |
| Shared libraries | n/a | |

## Test Coverage
Docs only. Checked every path and relative link on the page exists in the tree, and read CI's Documentation Build
(pass). #437's `data-freshness.md` and #439's `read-only-database-role.md` link to this page, so merge this one first.

## Verdict
Approve with nits. The one wrong reference is fixed; the gap sections should be refreshed as #426 to #428 land.
