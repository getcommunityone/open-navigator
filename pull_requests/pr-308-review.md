---
pr: 308
branch: fix/307-ballotpedia-import-without-pyspark
title: "fix(scrapers): let the Ballotpedia module import without pyspark"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve-with-nits
---

# PR Review: fix(scrapers): let the Ballotpedia module import without pyspark

## Summary

`scrapers.ballotpedia.ballotpedia_integration` raised `NameError` on import whenever pyspark was missing, which is
every environment installed from `requirements.txt`. A method's argument annotation named `SparkSession`, and that
name exists only when the guarded pyspark import succeeds. The PR quotes that annotation and imports `Any`, which the
file already used. A subprocess test blocks pyspark and checks the module and one importer load. Four root test
files that couldn't be collected now can be. Closes #307. Approve, with one nit for later.

## Scope of Change

- Files changed: 2 (+36 / -2)
- Areas touched: packages (scrapers), tests
- Commits: 6b626135 fix(scrapers): let the Ballotpedia module import without pyspark
- Range reviewed: `e32e3cdc..6b626135`

## CI Status

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success (it doesn't run `tests/` or `packages/scrapers/tests`, see #305) |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Docker Build Test (Full Stack) | skipped (no Docker files changed; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none.
- Personal data: none.
- Destructive or bulky changes: none.

## Strengths

- The test blocks pyspark in a subprocess, so it holds whether or not pyspark is installed and doesn't disturb
  other tests' imports.
- The PR compares failing-test lists before and after across the whole root folder, so the 3 newly visible failures
  are shown to be hidden network tests, not regressions.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- `packages/scrapers/src/scrapers/ballotpedia/ballotpedia_integration.py`: quoting fixes the one annotation that
  broke. A `from __future__ import annotations` at the top would stop every annotation in this 1,400-line module from
  being evaluated at import, so the next optional-import annotation can't break it again. I checked that the module
  defines no pydantic models or dataclasses that read annotations at runtime, so that change would be safe. Left out
  here to keep the diff to the bug.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #307 has Problem, Done when, Contract and Read first; branch `fix/307-...`; `Closes #307` |
| Conventional Commits | Yes | `fix(scrapers): ...` with the co-author trailer |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | A two-line change in an existing package module; nothing added to `scripts/` |
| Tests | Yes | The regression test failed before the fix (`NameError`) and passes after |
| Shared libraries | Yes | `packages/scrapers/tests` was run. It has 2 collection errors (`aiolimiter` missing), the same on `main`. The dependent root tests were run too |

## Test Coverage

Run locally on Python 3.12.3, with the repo root and every `packages/*` folder (and its `src`) on `PYTHONPATH`:

- `tests/test_ballotpedia_import_without_pyspark.py`: 2 passed. Before the fix, both failed with `NameError`.
- The four root test files that couldn't be collected: 6 passed, 3 failed. The 3 fetch live county websites and the
  sandbox's proxy blocks them.
- Whole root folder: the only new failures are those 3. One unrelated test went from failing to passing.
- `ruff check --select F821`: clean. The file passes `py_compile`.

## Verdict

Approve with one nit. Every required check is green on `6b626135`. The owner merges.
