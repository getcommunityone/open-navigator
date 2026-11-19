---
pr: 579
branch: fix/447-trending-locks
title: "fix(api): drop each trending inflight lock when its last waiter leaves"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve
---

# PR Review: fix(api): drop each trending inflight lock when its last waiter leaves

## Summary
The trending routes keep one `asyncio.Lock` per cache key to dedupe concurrent fills, and `?city=` is free text, so
the map `_inflight_locks` grew by one entry per distinct city for the life of the process (#447). The PR adds an
`_inflight(cache_key)` async context manager that counts the users of a key and removes the lock when the last one
leaves, and only if the map still holds that same lock. The three call sites use it. I traced the logic (no `await`
between `setdefault` and the count increment, cleanup in `finally` so a failed or cancelled fill still cleans up),
reproduced the tests, and confirmed the new tests fail on the old code. No findings that block or need a change.
The second half of #447 (NTEE causes) is split to #578 on purpose and #447 stays open. Verdict: approve.

## Scope of Change
- Files changed: 2 (+89 / -7, no generated files)
- Areas touched: api (`api/routes/trending.py`), tests (`tests/test_api_trending.py`)
- Commits:
  - `0ba127df` fix(api): drop each trending inflight lock when its last waiter leaves
  - `18e2b2dc` test(api): time-box the inflight lock test so it fails instead of hanging
- Range reviewed: `0ba4fcd2..18e2b2dc` (base is `main`; BASE_SHA is the merge base with `origin/main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required; no Docker files change) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. A keyword scan of the diff (password, token, secret, api_key, DSNs) found nothing.
- **Fabricated data in a served path:** clean. No numbers or values are produced; the change is lock bookkeeping.
  Test city names ("City 0" ... "City 199") are in tests only.
- **Personal data:** clean. A `?city=` value is used only as a cache key and is now released sooner.
- **Destructive or bulky data changes:** clean. No data, cache or file changes, and nothing under `data/cache/`.

## Strengths
- Fixes the cause (a map that only grows) rather than adding a cap, and keeps the existing dedupe: concurrent fills
  of one key still share a lock (the existing dedupe test passes).
- The remove-by-identity check (`_inflight_locks.get(cache_key) is lock`) means a request holding an older lock can
  never delete a newer one.
- Cleanup sits in `finally`, so an exception or a cancellation while waiting still decrements the count.
- One helper replaces three copies of the same two lines, so the three routes can't drift apart.
- The tests assert behaviour through the public route (200 distinct cities leave both maps empty), the failure
  path, and the waiter and newer-lock cases. The second commit adds `wait_for` timeouts so a regression fails
  instead of hanging CI.
- The PR body uses `Refs #447` and names the split follow-up (#578), as `AGENTS.md` asks.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
None worth a change. One observation, checked and not raised as a finding: `clear_trending_cache()` clears the lock
map and the counter while requests may be in flight. The only caller outside `trending.py` is the tests, so I traced
the interleavings by hand. The worst case is that two requests briefly don't share a lock, and they would then both
fill the cache, which is harmless. No lock leaks in any order I traced.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/447-trending-locks`; body says `Refs #447` (one part of a larger issue); #447 has Problem, Done when, Contract, Read first; the NTEE half is its own issue (#578) |
| Conventional Commits | Yes | `fix(api): ...` and `test(api): ...`, both with the co-author trailer |
| No fabricated data | Yes | Scan above |
| New Python in `packages/` | n/a | Edits an existing API route; nothing added to `scripts/` |
| dbt for transformations | n/a | No SQL changes |
| Naming | n/a | No names exposed |
| Keys | n/a | No tables |
| Calendar years | n/a | |
| Scope label matches filter | n/a | No UI change |
| Match evidence on filtered tiles | n/a | |
| Docs | n/a | Internal fix, no docs needed; no new `.md` files |
| Telemetry and logging | Yes | Existing spans untouched; no logging added or needed |
| Tests | Yes | 3 new tests fail on the old code, pass on the fix (reproduced below) |
| Shared libraries | n/a | `api/` only, nothing in `packages/` |

## Test Coverage
- **Run locally** (clean worktree, `PYTHONPATH` forced to the worktree):
  - `pytest tests/test_api_trending.py`: 11 passed.
  - `pytest tests/test_api_cpi.py tests/test_api_efile990.py` (sibling routes with their own `_inflight_locks`,
    untouched here): 9 passed.
  - `ruff check api/routes/trending.py tests/test_api_trending.py`: clean.
  - **Fail-before check:** with `api/routes/trending.py` reverted to the merge base, `test_api_trending.py` gives
    3 failed, 8 passed; the 3 failures are the 3 new tests (they reference `_inflight` / `_inflight_users` and
    assert the maps empty). The file was restored with `git checkout`; the worktree was clean afterwards.
- **Covered:** no growth across many distinct cities, cleanup on a failed fill, a waiter keeping the lock alive, and
  a newer lock never removed by an older holder.
- **Not covered:** cancellation while waiting for the lock, and `clear_trending_cache()` during an in-flight request.
  Both are reasoned correct above and neither is needed for the fix.
- **PR body claims:** "11 pass", "3 new tests fail on the old code and pass on the fix" and "ruff clean" all
  reproduced. The "dangling symlink breaks collection in my checkout" statement is unverified here, since the
  review used a clean worktree.
- No frontend or dbt changes, so `tsc` and `dbt ls` were not needed.

## Verdict
**approve.** No changes required. Required checks are green on `18e2b2dc`. #447 stays open for the NTEE half
(#578).
