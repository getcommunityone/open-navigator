---
pr: 312
branch: fix/311-pipeline-index-technical-summaries
title: "fix(llm): collect technical meeting summaries where the output list is built"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve-with-nits
---

# PR Review: fix(llm): collect technical meeting summaries where the output list is built

## Summary

The end-of-run output index appended technical meeting summaries to `found`. That list exists only in
`collect_pipeline_outputs`, so the index raised `NameError` as soon as any summary existed. The jurisdiction pipeline
catches only `ImportError`, so its run failed after "All jurisdictions complete" and skipped the safety review. The
PR moves the loop, unchanged, into `collect_pipeline_outputs`. The index's existing "Technical manifests" section
can now print. Three new tests cover the collector, the index and the empty case. Closes #311. Approve, with one nit.

## Scope of Change

- Files changed: 2 (+71 / -10)
- Areas touched: packages (llm)
- Commits: ed1d9996 fix(llm): collect technical meeting summaries where the output list is built
- Range reviewed: `e32e3cdc..ed1d9996`

## CI Status

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success (it doesn't run `packages/llm/tests`, see #305) |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Docker Build Test (Full Stack) | skipped (no Docker files changed; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none. The test writes placeholder Markdown files in a temp folder.
- Personal data: none.
- Destructive or bulky changes: none. The tests write only under pytest's `tmp_path`.

## Strengths

- The fix moves the loop rather than defining `found` in the index. Defining `found` there would have stopped the
  crash, but the technical files would still never be listed, because the index groups artifacts by kind before that
  loop ran.
- The tests use the real folder layout the pipeline writes (`.../meetings/<date>/session/`), and they check the
  printed section headings.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- `packages/llm/src/llm/governance/pipeline_output_links.py:49-50`: `if p.name == "_meeting_summary_technical.md":
  continue` can never be true. The loop above it is `rglob("_meeting_summary.md")`, which matches only that exact
  file name. It predates this PR and does no harm, so it was left alone to keep the diff to the bug.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #311 has Problem, Done when, Contract and Read first; branch `fix/311-...`; `Closes #311` |
| Conventional Commits | Yes | `fix(llm): ...` with the co-author trailer |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | The change and its test are both in the llm package |
| Telemetry and logging | n/a | The function prints a cheat sheet for a notebook user, as before |
| Tests | Yes | Before the fix, 2 of the 3 new tests failed (`NameError`, and missing artifacts). All 3 pass after |
| Shared libraries | Yes | `packages/llm/tests`: 124 passed. On `main`, only the new tests fail. The 8 root test files that import `llm`: 67 passed |

## Test Coverage

Run locally on Python 3.12.3, with the repo root and every `packages/*` folder (and its `src`) on `PYTHONPATH`:

- `packages/llm/tests/test_pipeline_output_links.py`: 3 passed.
- `packages/llm/tests`: 124 passed.
- Root tests that import `llm` (8 files): 67 passed.
- `ruff check --select F821`: clean. The file passes `py_compile`.

Not covered by a test: the call from `jurisdiction_pipeline.py`. It passes keyword arguments that match the
function's signature, which was read and not changed.

## Verdict

Approve with one nit. Every required check is green on `ed1d9996`. The owner merges.
