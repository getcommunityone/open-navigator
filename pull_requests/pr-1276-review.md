---
pr: 1276
branch: chore/1272-no-outside-org-refs
title: "chore(repo): add a third-party sources rule to AGENTS.md and remove an outside organization's name from the repo"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: general-purpose subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: chore(repo): add a third-party sources rule to AGENTS.md and remove an outside organization's name from the repo

## Summary
The PR adds a "Third-party sources" rule to AGENTS.md and removes the organization's name from every other tracked file. It changes comments, dbt descriptions, the regenerated ODCS contract, one test name, a prompt file, a past review and three docs pages. No hashed classifier text changed: all five `question_version`s match the pinned values, water-fluoridation `5a7828a925fd` included. The reviewer found one doc snippet that would break when copied, and it was fixed on the branch. The verdict is approve-with-nits. This PR changes the agent rules, so under AGENTS.md it waits for the owner to say "merge".

## Scope of Change
- Files changed: 17 (AGENTS.md, Python comments, dbt SQL/YAML descriptions, ODCS contract, one Python test, one TS test comment, a prompt file, a past review, three docs pages, this review)
- Areas touched: agent rules, api (comment), dbt_project, packages (llm), scripts (docstring), web_app (test comment), web_docs, prompts
- Range reviewed: `origin/main...chore/1272-no-outside-org-refs`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The logo URLs keep the placeholder `token=XXX`.
- **Fabricated data:** clean. The docs examples now use placeholders (`<ein>`, `<total revenue>`, `example.org`) instead of figures that look real. No served path was touched.
- **Personal data:** clean.
- **Destructive data changes:** clean. No warehouse rows or tables were touched.

## Strengths
- The `question_version` hashes are pinned in a test, so the comment-only edits to `topic_lean.py` are proven not to trigger a paid re-read.
- The contract was regenerated with `python -m models.odcs --write`, and `--check` passes.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None outstanding.
- Fixed on the branch: in `web_docs/docs/guides/form-990-enrichment.md`, the new `print` line inside the `python -c "..."` block had unescaped double quotes. They are now escaped like the lines around it.

### 🔵 Nits / suggestions (Minor)
- Fixed: `api/routes/search_postgres.py` no longer lists a made-up name next to real leaked examples.
- Fixed: the docs snippet variable `cq` is renamed to `org`.
- Left as is: the hashed `sides` text in `topic_lean.py` (`TOPICS["water-fluoridation"]`) still says "as in the national poll question 'Which of the following comes closest to your position?'". It doesn't name the organization. Changing it would change the hash and force a paid re-read, so the owner decides.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `chore/1272-...`, `Closes #1272`, and the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | Placeholders, not figures |
| New Python in `packages/` | n/a | Comment and test-name edits only |
| dbt for transformations | n/a | Descriptions only; `dbt parse` passes |
| Keys / naming / calendar years | n/a | |
| Scope label / match evidence | n/a | No UI surface changed |
| Docs | Yes | The three docs pages are updated in this PR |
| Agent-rule change | Yes | Waits for the owner to say "merge" |
| Shared libraries | Yes | The llm topic-lean tests pass |

## Test Coverage
Run locally:
- `pytest packages/llm/tests/test_topic_lean.py`: 16 passed, with the same hashes.
- `python -m models.odcs --check`: 98 contracts current and valid.
- `dbt parse`: passes.
- web_app `vitest run`: 77 files, 717 tests passed. `tsc --noEmit` is clean.
- web_docs `npm run build`: succeeds.

## Verdict
**approve-with-nits.** Nothing is blocking. This PR changes the agent rules, so it merges only after the owner says "merge".
