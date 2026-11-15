---
pr: 347
branch: fix/48-policy-cache-cleanup-converge
title: "fix(llm): stop the policy-cache date cleanup re-appending .diagrams to diagram files"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: python-packages-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(llm): stop the policy-cache date cleanup re-appending .diagrams to diagram files

## Summary
Fixes #48: `fix_policy_cache_dates_from_title` never converged because `_parse_dated_basename` used `Path.stem`, so `x.diagrams.md` parsed to the title `x.diagrams` and every run renamed the file to `x.diagrams.diagrams.md`. The first commit (6b43ae2) fixed that but also stripped the caption-sidecar suffixes. The reviewer found that this pointed each sidecar at its main transcript, so `_safe_move` overwrote or deleted one with the other, and the coordinator reproduced it. That was data loss in `data/cache/`, so it blocked. Fixed in 738dc44: sidecars are no longer stripped, and a regression test seeds sidecars and checks the whole file set and its contents are unchanged. With that, the change works on synthetic folders. It has not been run on the real cache, so the verdict is approve-with-nits.

## Scope of Change
- Files changed: 2 (+117 / -1)
- Areas touched: packages (llm)
- Commits:
  - 6b43ae2 fix(llm): stop the policy-cache date cleanup re-appending .diagrams to diagram files
  - 738dc44 fix(llm): keep caption sidecars out of the compound-suffix strip
  - 061bfa0 test(llm): sort imports in the cleanup idempotence test
- Range reviewed: `b448a7c..061bfa0`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | ✅ success (061bfa0) |
| Documentation Build | ✅ success (061bfa0) |
| Backend Tests | ⏳ running on 061bfa0 (✅ on 6b43ae2) |
| API Types | ⏳ running on 061bfa0 (✅ on 6b43ae2) |
| PR conventions | ✅ success (061bfa0) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean (meeting titles appear only in the test).
- Personal data: clean.
- Destructive data changes: **found in 6b43ae2 and fixed in 738dc44.** A newer `X.caption_raw_data.json` replaced `X.json`; an older one was deleted as an "older duplicate". The code no longer deletes anything it didn't delete before this PR.

## Strengths
- The root cause is identified exactly and explained in the code comment and the PR description.
- The tests fail on `main` (3 of 3) and on 6b43ae2 (the 2 sidecar tests), and pass on the head.
- The sidecar test compares names and contents across runs, so it catches lost files, not just moves.

## Findings
### 🔴 Blocking (Critical)
- ~~`transcript_cache_paths.py:1491-1509` (6b43ae2): stripping `.caption_raw_data.json` / `.caption_formatted.json` lets a sidecar overwrite or delete its transcript.~~ **Fixed in 738dc44.** Verified by reproduction: on 6b43ae2 the run reported `moved: 1` and left the raw caption list in `X.json`. On `main` and on 061bfa0 both files are untouched (`already_named: 2`).
### 🟡 Should fix (Important, non-blocking)
- ~~`test_policy_cache_cleanup_idempotent.py`: the seed data had no sidecars, and the tests counted moves only.~~ **Fixed in 738dc44** (`test_caption_sidecars_are_never_merged_into_the_transcript`, sidecar newer and older).
### 🔵 Nits / suggestions (Minor)
- Not run against the real `data/cache/` tree (it isn't reachable from the review session). Before a real run, run `python -m llm.gemini.cleanup_policy_transcript_cache --dry-run` twice and confirm the second run reports ~0 moves. Diagram files already renamed with a repeated `.diagrams` will be renamed once more, to the clean name.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/48-…`, `Closes #48`; four parts added to #48 under a dated note |
| Conventional Commits | ✅ | All three, with co-author trailers |
| No fabricated data | ✅ | |
| New Python in `packages/` | ✅ | Nothing in `scripts/` |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label / Match evidence | n/a | |
| Docs | n/a | |
| Telemetry and logging | n/a | No new logging |
| Tests | ✅ | Regression tests for both bugs |
| Shared libraries | ⚠️ | `packages/llm` suite run; the dependent `packages/scrapers` suite was not run locally (CI Backend Tests covers it) |

## Test Coverage
- Ran locally: `packages/llm` — 178 passed, 2 failed. The 2 failures are in `test_meeting_gap_analysis.py` and fail the same way on `main`.
- New tests: 5. They fail before the fix and pass after it.
- `ruff check` on the new test is clean. The module has older ruff findings, none on the changed lines.

## Verdict
**approve-with-nits.** The blocking data-loss bug found in review is fixed and covered by a test. Before the first real run, do the double `--dry-run` on the real cache, and merge once Backend Tests finishes green on 061bfa0.
