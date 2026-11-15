---
pr: 325
branch: ci/305-run-root-tests
title: "ci(backend): run the root tests and every package's tests in Backend Tests"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve-with-nits
---

# PR Review: ci(backend): run the root tests and every package's tests in Backend Tests

## Summary

Backend Tests now runs `pytest` over `pytest.ini`'s test paths: the root `tests/` folder and eight package test
folders. Before, it ran only `packages/datamodels/tests`. The job installs the test imports that `requirements.txt`
lacks. Every failure from the November 14 triage is handled by its cause, and no test is simply silenced:
- live tests are opt-in;
- tests that need local data skip when it's missing;
- three test bugs are fixed;
- two disputed tests are `xfail` pointing at the owner's decision, #322.

Locally the set gives 1345 passed, 41 skipped and 2 xfailed. Closes #305. Approve, with nits.

## Scope of Change

- Files changed: 19 (+116 / -16): the workflow, `pytest.ini`, `conftest.py`, 16 test files
- Areas touched: ci, tests
- Commits: eae2898c ci(backend): run the root tests and every package's tests in Backend Tests

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. No credential is added to the workflow, and live tests are off by default, so CI calls no
  third-party site.
- Fabricated data: none.
- Personal data: none.
- Destructive changes: none. The data-dependent tests only check whether `data/cache/...` exists and never write to
  it.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None in this PR. Two follow-ups are filed: #321 (commit the NTEE seed with its source) and #322 (the owner's call on
two YouTube rules).

### 🔵 Nits / suggestions (Minor)

- The three test-only installs (`aiolimiter`, `aiosqlite`, `h2`) live in the workflow, not in `requirements.txt`. A
  developer who runs `pytest` after `pip install -r requirements.txt` hits import errors for the core-lib tests.
  They're left out of `requirements.txt` here because changing that file also triggers the Docker build. A
  `requirements-dev.txt`, or adding them there, is a reasonable follow-up.
- `test_policy_analyzer.py` is a demo script collected as a test. Marking it `live` keeps it out of CI. Moving it out
  of the test paths would be cleaner.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #305 has all four parts, plus dated additions with the triage; `Closes #305` |
| Conventional Commits | Yes | `ci(backend): ...` with the co-author trailer |
| Settings change by PR | Yes | The PR says which environments change: CI only |
| Tests | Yes | No failing test is deleted. Each is fixed, skipped for a stated missing resource, or `xfail` with an issue |

## Verdict

Approve with nits, once CI's own run is green. That run installs the full `requirements.txt`, which the local check
couldn't.
