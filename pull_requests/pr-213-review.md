---
pr: 213
branch: fix/location-resolution-reliability
title: "fix(location): harden geocoding and profile hydration"
author: BlueHopper6
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: fix(location): harden geocoding and profile hydration

## Summary
Makes the geocode proxy (`api/routes/geocode.py`) sturdier, and fixes `LocationContext` so a signed-in user's profile location is applied once `/auth/me` resolves.
- **Geocode proxy:**
  - Identical lookups made at the same time now share one upstream call (the cache is re-checked inside the lock).
  - Timeouts and connection errors return 502s instead of 500s, and a failed call still counts toward Nominatim's rate budget.
  - A 429 forwards a numeric `Retry-After`.
  - `countrycodes` is validated, and whitespace-only queries are rejected.
- **`LocationContext`:** before, it checked the profile only on first mount, before auth had loaded, so a profile location was missed. It now waits for auth, keeps a manual selection taking precedence, and clears a corrupt stored value instead of getting stuck on it.

The branch was 8 weeks behind; `main` was merged in, keeping `main`'s versions of the three TypeScript files it had fixed separately.

## Scope of Change
- Files changed after the merge: `api/routes/geocode.py`, `tests/test_geocode_proxy.py`, `web_app/src/contexts/LocationContext.tsx` (plus a one-line `AddressLookup.tsx` change)
- Areas touched: api, web_app, tests

## CI Status
See the PR's checks on the merge commit.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. Personal data: unchanged handling (a location in localStorage and the user profile). No fabricated data. No destructive changes.

## Strengths
- Recording the call time in `finally` stops an outage from turning into a tight retry loop against Nominatim.
- Only an integer `Retry-After` is forwarded, so no upstream header text is reflected.
- Nine offline tests cover coalescing, cache reuse, network failures, 429, malformed JSON and normalization.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The upstream call now happens while holding `_throttle_lock`, so all geocode requests are serialized for the duration of each call (up to the 10 s timeout). That matches Nominatim's one-request-per-second policy, but one slow upstream call will now delay every waiting user. Acceptable at current traffic.
- The `LocationContext` effect now re-runs on every auth change and re-reads localStorage each time. Harmless, but slightly more work than needed.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partly | "Related to #147" (closed); predates the rule |
| Conventional Commits | ✅ | |
| Logging | ✅ | `loguru` warnings on upstream failures |
| Tests | ✅ | 9 offline tests |

## Test Coverage
- `pytest tests/test_geocode_proxy.py`: 9 passed after the merge.
- `npx tsc --noEmit`: clean after the merge.

## Verdict
**approve-with-nits.** Merge when CI is green.
