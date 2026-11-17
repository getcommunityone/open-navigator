---
pr: 438
branch: fix/427-analysis-prompt-version
title: "fix(llm): derive each analysis's prompt_version from the prompt's content"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review in a fresh worktree; each finding traced in the code)
verdict: approve-with-nits
---

# PR Review: fix(llm): derive each analysis's prompt_version from the prompt's content

## Summary
Adds `llm.prompt_version` (`prompt_sha256`, `prompt_file_sha256`, `prompt_version_label`, `prompt_version_from_meta`),
records `prompt_sha256` in each analysis meta file, and makes both loaders write `<prompt name>@<first 12 hex>` (or
`<name>@unrecorded` for older analyses) and update it on conflict. It works and matches issue #427's contract. One real
bug: a name longer than 37 characters cut the label at 50 and dropped the hash, so the version stopped changing with
the prompt. Fixed on the branch with a regression test. Approve with nits.

## Scope of Change
- Files changed: 5 (+98 / -3)
- Areas touched: packages (llm)
- Commits:
  - 0db15a34 fix(llm): derive each analysis's prompt_version from the prompt's content
  - d68b3397 fix(llm): keep the prompt hash when a long name is shortened to fit the column (review fix)
- Range reviewed: `fb865cc2..0db15a34`, then the fix

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker changes) |

CI was read on 0db15a34; the fix commit triggers a new run.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. Old analyses get `@unrecorded`, never an invented version.
- Personal data: clean.
- Destructive or bulky data changes: clean. The loaders' upsert now updates `prompt_version`; that is the intended
  change, done by the existing loaders.

## Strengths
- `@unrecorded` for analyses saved before the hash existed, instead of back-dating a version.
- The hash is of the prompt file's bytes at save time, recorded in the meta file next to the analysis.
- Small module with a clear contract; both loaders and the saver use it.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Fixed (d68b3397).** `packages/llm/src/llm/prompt_version.py`, `prompt_version_label`: the label was built as
   `f"{stem}@{sha[:12]}"[:MAX_LEN]`. For a name over 37 characters the cut removed part or all of the hash; with an
   80-character name the label was 50 `x`s and identical for every prompt version. The old test
   (`test_long_names_fit_the_column`) checked only the length. Now the name is shortened and the `@<sha12>` /
   `@unrecorded` suffix is kept. The new test `test_long_names_fit_the_column_and_keep_the_hash` failed on the old code
   (1 failed, 3 passed) and passes on the fix.

### 🔵 Nits / suggestions (Minor)
1. **Left.** `load_meeting_transcripts.py:511` hashes `self.prompt_template`, read with `open(..., 'r')` (universal
   newlines), while `save_transcript_policy_output` hashes the file's raw bytes. The two agree only while the prompt
   file has LF line endings. `prompt_file_sha256(POLICY_ANALYSIS_PROMPT)` would make them match by construction.
   `Path(str(POLICY_ANALYSIS_PROMPT)).stem` is also just `POLICY_ANALYSIS_PROMPT.stem`.
2. **Left.** In `load_analysis_cache_to_bronze.py`, a meta file with neither `prompt_name` nor `prompt_file` now
   writes `prompt_version = NULL` over an existing `v1.0`. That is honest (the version is unknown), but different
   from the "38 rows keep v1.0" in the PR body, which covers analyses with no meta file at all (those are skipped
   before the upsert).
3. **Left.** In `load_meeting_transcripts.py` the new import sits between third-party imports. Ruff doesn't flag it;
   the file's 6 ruff errors are all from before this PR.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `fix/427-analysis-prompt-version`; `Closes #427`; the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | `packages/llm/src/llm/prompt_version.py` |
| dbt for transformations | Yes | Loader-side only, no SQL logic moved into Python |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | n/a | |
| Telemetry and logging | Yes | loguru, unchanged |
| Tests | Yes | 4 tests, plus the regression test added here |
| Shared libraries | Yes | `packages/llm` tests run; the only reference from another package (`ingestion.youtube.promote_to_c1_event`) is a docstring |

## Test Coverage
Ran locally: `pytest packages/llm/tests -q` → 189 passed (pytest.ini's `pythonpath` puts the worktree's `packages/*/src`
first, so the PR's code was tested). `ruff check` on the changed files: 9 errors, the same 9 as on the base commit,
none new. Not run: the warehouse reload the PR describes (no warehouse writes in this review).

## Verdict
Approve with nits. The truncation bug is fixed and tested; the hashing mismatch in `load_meeting_transcripts.py` is
worth a follow-up.
