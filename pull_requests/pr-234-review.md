---
pr: 234
branch: fix/233-deploy-lfs-objects
title: "fix(deploy): fetch Git LFS objects before the Hugging Face push"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review, verified by tests and a rehearsal on main)
verdict: approve
---

# PR Review: fix(deploy): fetch Git LFS objects before the Hugging Face push

## Summary

Deploy run 9 failed at the push to Hugging Face because git-lfs had no object for
`web_docs/static/img/erd/marts_full.png` (#233). The deploy clone skips LFS smudge, so LFS-stored files are staged
as pointers with nothing behind them. This PR fetches the staged pointers' objects from the source checkout's
origin before the commit, and drops any pointer whose object still can't be found. It works: 5 tests pass, and a
rehearsal on `main` fetched all 177 pointers (29 MiB) in 7 seconds and dropped none. The verdict is approve.

## Scope of Change

- Files changed: 3 (one new helper, the deploy script, one new test file), no generated files
- Areas touched: hosting (deploy), tests
- Commits: ae1a71a fix(deploy): fetch Git LFS objects before the Hugging Face push
- Range reviewed: `main` (3dd03ed) to ae1a71a

## CI Status

Checked green on the head before merging (Frontend Build, Documentation Build, Backend Tests, API Types). CI's
Backend Tests job compiles and imports but doesn't run pytest, so the new tests were run locally: 5 passed.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. The origin URL is passed to the clone in an environment variable and never printed, because a
  laptop's origin URL can carry a token. `HF_TOKEN` handling is unchanged.
- **Fabricated data in a served path:** clean. Nothing served changes.
- **Personal data:** clean.
- **Destructive data changes:** none. `git rm --cached` only unstages files in the throwaway deploy clone.

## Strengths

- It fixes the cause, not the symptom. The images reach the Space instead of being dropped, and the drop is only a
  safety net for an object that's missing everywhere.
- Fetching is best effort and the drop is explicit, so a single bad pointer can't block a deploy again, and the log
  names any file it excludes.
- The tests reproduce the real failure: a skip-smudge `--local` clone, staged on an orphan branch, with one fetchable
  object and one that's gone.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **The pointer scan spawns `git cat-file` per staged file.** On a whole-repository index (2,363 files) it takes
   about 9 seconds, and it runs twice. That's fine for a deploy, but `git cat-file --batch-check` would make it one
   process if the repository grows.
2. **CI never runs these tests.** The Backend Tests job only compiles and imports. Running `pytest packages/` in CI
   would catch a regression here. That deserves its own issue, because it touches every package.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| Issue first, four parts (AGENTS.md) | ✅ #233 |
| Branch `<type>/<issue>-<slug>`, `Closes #<issue>` | ✅ `fix/233-deploy-lfs-objects`, `Closes #233` |
| Test first | ✅ the 5 tests failed before the helper existed |
| Conventional Commits | ✅ |
| New Python in `packages/`, not `scripts/` | ✅ the tests live in `packages/hosting/tests`; the helper sits beside the deploy script it serves |
| No Fabricated Data | ✅ n/a |

## Test Coverage

`packages/hosting/tests/test_deploy_lfs_objects.py`: both scripts parse as bash; pointers are listed with their oids;
fetch-then-drop keeps the fetchable image and drops the missing one; drop without fetch drops both; the deploy
script fetches, then drops, before it commits and pushes, and passes `HF_DEPLOY_LFS_REMOTE`. The fetch from GitHub
itself was rehearsed on `main`, not unit-tested, because it needs the network.

## Verdict

**Approve.** Merge when the four required checks are green, then re-run the deploy on `main`.
