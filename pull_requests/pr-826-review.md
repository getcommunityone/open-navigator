---
pr: 826
branch: fix/825-retry-empty-analysis
title: "fix(llm): redo an empty or broken analysis file on the next analysis run"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve
---

# PR Review: fix(llm): redo an empty or broken analysis file on the next analysis run

## Summary
The analysis stage skipped a video whenever its analysis file existed, so an empty file from an interrupted run was
never redone and the loader reported it as unreadable on every run. The PR adds a cheap usability check (the file
must start with a JSON object) and lets an unusable file be analysed again. Small, tested, and the behaviour for real
analysis files is unchanged. Approve.

## Scope of Change
- Files changed: 5 (excluding this review)
- Areas touched: packages (llm) / api / tests / web_docs
- Commits: `28805344` fix(llm): redo an empty or broken analysis file on the next analysis run
- Range reviewed: `origin/main...origin/fix/825-retry-empty-analysis`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. The redo overwrites a file that holds no analysis; nothing in `data/cache/` is deleted.

## Strengths
- Reads 256 bytes per file instead of parsing it, so the check costs little over thousands of files.
- The evidence is the owner's own loader log.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- A file that starts with `{` but is cut off later still counts as analysed. Stated in the PR; catching it means
  parsing every file on every run.
- Paid compute: the change starts no run. In a run a person launches, each unusable file costs one extra model call.
  The owner's cache had one such file in 12,169, so the cost is negligible, and it is stated in the PR body.
- Traced by reading: after the warning the code falls through to the full-tier eligibility check and yields the video;
  the usable-file branch still ends in `continue`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #825 with the four parts; branch `fix/825-retry-empty-analysis`; `Closes #825` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | |
| Docs | Yes | `web_docs/docs/development/batch-load-tab.md` |
| Telemetry and logging | Yes | loguru warning names the file |
| Tests | Yes | Nine cases for the check; the skip branch itself is covered by reading, not by a test |
| Paid compute | Yes | No run started |

## Test Coverage
`pytest tests/test_loader_gate_796.py tests/test_load_tab_counts_823.py`: 52 passed. Not run: an analysis run.

## Verdict
approve.
