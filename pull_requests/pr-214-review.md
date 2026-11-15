---
pr: 214
branch: fix/feed-zip-place-resolution
title: "fix(feed): mount feed router and resolve US ZIP queries to municipalities"
author: BlueHopper6
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: fix(feed): mount feed router and resolve US ZIP queries to municipalities

## Summary
Fixes a live bug: `api/main.py` imports `api.routes.feed` (line 361) but never mounts its router, so every `/api/feed/*` call (feed setup's place search and config) returns 404 on `main` today. Verified on `origin/main`: there is an import and no `include_router(feed_routes…)`. The PR mounts it and makes `GET /api/feed/places` resolve 5-digit ZIPs (and ZIP+4) to municipalities, using Nominatim's structured `postalcode` search plus a reverse lookup on the centroid. It reuses the geocode proxy's throttled, cached `_throttled_get`, so Nominatim's rate limit is respected. Feed setup chips now read "City, ST". The branch was 5 weeks behind; `main` was merged in (conflicts resolved by keeping `main`'s TypeScript fixes and mounting both the feed and the new data-centers routers).

## Scope of Change
- Files changed after the merge: `api/main.py`, `api/routes/feed.py`, `tests/test_feed_places.py`, `web_app/src/pages/FeedSetup.tsx`, `web_app/src/components/AddressLookup.tsx`
- Areas touched: api, web_app, tests
- Range reviewed: `origin/main..fix/feed-zip-place-resolution` (after the merge commit)

## CI Status
See the PR's checks on the merge commit (CI re-runs on push).

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Results come from Nominatim; nothing is invented when a lookup fails.
- Personal data: the ZIP is sent to Nominatim, as free-text place search already was. No new storage beyond the `User.city` the config endpoint already wrote.
- Destructive data changes: none.

## Strengths
- One-line fix for a real 404, with route tests.
- Reuses the shared throttle and cache rather than a second Nominatim client.
- Results are deduplicated by (city, county, state_code), so a ZIP doesn't list the same town twice.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `placeHitToChip` falls back to `shared_level: 'city'` when a hit has neither city nor county. A state-only hit would be saved as a city chip. Rare for ZIP or place searches.
- The placeholder example uses Tuscaloosa (`"e.g., Tuscaloosa, AL or 35401"`). It's example text, not a default, so it's fine under #147.
- Branch name predates the `<type>/<issue>-<slug>` rule; PR opened before Nov 14, so the conventions check doesn't apply.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partly | "Supports #147" (#147 is closed); no own issue. Predates the rule. |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | |
| API / OpenTelemetry | ✅ | Existing route instrumentation unchanged |
| Tests | ✅ | `tests/test_feed_places.py`: 5 passed locally after the merge |

## Test Coverage
- `pytest tests/test_feed_places.py`: 5 passed (offline; Nominatim mocked).
- `cd web_app && npx tsc --noEmit`: clean after the merge.

## Verdict
**approve-with-nits.** Merge when CI is green.
