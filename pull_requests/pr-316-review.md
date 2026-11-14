---
pr: 316
branch: fix/257-images-out-of-lfs
title: "fix(repo): keep 15 committed images out of LFS so checkouts stay clean"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(repo): keep 15 committed images out of LFS so checkouts stay clean

## Summary

Fifteen small images were committed as plain blobs, but the `*.png`, `*.jpg`, `*.svg` and `*.ico` rules sent them
through LFS. So every checkout showed them as modified and every clone warned about them. The PR keeps them plain
with a `-filter -diff -merge` line each, after the LFS rules, which is the same approach as #224. It adds a test
that every file the LFS rules claim is stored as a pointer. A fresh clone of the branch is clean. Closes #257.
Approve.

## Scope of Change

- Files changed: 2 (`.gitattributes`, `tests/test_gitattributes_lfs.py`)
- Areas touched: repo config, tests
- Commits: 81cbbb76 fix(repo): keep 15 committed images out of LFS so checkouts stay clean

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none.
- Personal data: none.
- Destructive or bulky changes: none. No blob changes and no storage move.

## Findings

None blocking, none to fix, no nits. Verified:
- The new test fails on `main` and lists exactly the 15 files named in #257.
- It passes on the branch.
- A fresh clone gives no warning and a clean `git status`.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #257 has Problem, Done when, Contract and Read first; `Closes #257` |
| Conventional Commits | Yes | `fix(repo): ...` with the co-author trailer |
| Tests | Yes | The regression test fails before the change and passes after |

## Verdict

Approve once the required checks are green. Whether the deploy still publishes these images can only be checked on
the next deploy run, as the issue says.
