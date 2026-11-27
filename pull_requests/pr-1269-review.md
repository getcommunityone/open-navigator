---
pr: 1269
branch: fix/1266-place-geojson-content-type
title: "fix(data-explorer): draw Cities & towns on the live site, where .geojson is served as octet-stream"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve
---

# PR Review: fix(data-explorer): draw Cities & towns on the live site, where .geojson is served as octet-stream

## Summary
The places tier of the Data Explorer map drew no towns on the live site because the vintage-fallback fetch kept a
response only when its content type said "json", and production serves `.geojson` as `application/octet-stream`
(Python's `mimetypes` has no entry for it). The PR replaces that check with "a 2xx that is not the HTML app page",
keeps real server errors loud, and registers `.geojson` as `application/geo+json` on the API's `/data` mount. Verified
in Firefox against a local Vite that serves `.geojson` as octet-stream, like production: towns go from 0 drawn to
12 shaded (Tuscaloosa County AL) and 5 shaded (Greene County GA). One Important finding from the reviewer was fixed
in 1418935c. Verdict: approve.

## Scope of Change
- Files changed: 6 code/docs (+106 / -27, excluding this review)
- Areas touched: api, web_app, web_docs, tests
- Commits:
  - eea1dc57 fix(data-explorer): draw Cities & towns on the live site, where .geojson is served as octet-stream
  - 1418935c fix(data-explorer): surface server errors in the census map's vintage fallback
  - 0dc56b84 docs(pr-1269): auto-write rubric review [skip review] (bot; superseded by this file)
- Range reviewed: `e90381b2..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | see PR checks on the head commit (merge only when green) |
| Documentation Build | see PR checks |
| Backend Tests | see PR checks |
| API Types | see PR checks |
| PR conventions | see PR checks |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. A town or ZIP with no value keeps the "no data" fill
  (`rgba(248,250,252,0.40)`); the 5 grey ZIPs in Tuscaloosa County are Census-suppressed (`-666666666`) or absent.
- Personal data / privacy: clean (census aggregates only).
- Destructive or bulky data changes: none; no data files committed.

## Strengths
- Root cause found by comparing prod and local responses, not guessed: `2022/place_01.geojson` is
  `200 application/octet-stream` on prod and `application/geo+json` under Vite.
- Fixed on both sides: the client no longer depends on the server's label, and the server now sends the right one.
- The acceptance rule is a pure, tested helper shared with `fetchStaticJson`.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- (Fixed in 1418935c) `CensusDrilldownMapPage.tsx` place-geojson and ZCTA-metric loops: the first commit `continue`d on
  every non-2xx, so a 5xx/403 looked like "no data". Now `servedDataFileStatus()` returns `missing` only for 404 or the
  HTML page; other failures throw. Verified by reading the loops and by the new unit test.

### 🔵 Nits / suggestions (Minor)
- (Fixed in 1418935c) A 2xx body that isn't JSON aborted the whole fallback; it now moves on to the next vintage.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1266 has all four parts; branch `fix/1266-…`; `Closes #1266` (and #1097, same cause) |
| Conventional Commits | Yes | co-author trailer on agent commits |
| No fabricated data | Yes | no-data fill kept for missing values |
| New Python in `packages/` | N/A | API module edit only |
| dbt for transformations | N/A | |
| Naming / Keys / Calendar years | N/A | |
| Scope label matches filter | Yes | unchanged; breadcrumb and data still move together |
| Match evidence on filtered tiles | N/A | |
| Docs | Yes | `web_docs/docs/guides/data-explorer-matrix-map.md`, "When the Data explorer shows no data" |
| Telemetry and logging | N/A | |
| Tests | Yes | `fetchStaticJson.test.ts` (octet-stream accepted, HTML/404 missing, 5xx/403 error) and `tests/test_static_cache.py` (`.geojson` → `application/geo+json`); both fail on the old code |
| Shared libraries | N/A | no `packages/` change |

## Test Coverage
Run locally: `npx vitest run` (77 files, all passed), `npx tsc --noEmit` (no errors in touched files),
`pytest tests/test_static_cache.py tests/test_restore_lfs_static.py` (passed), `ruff check` on changed Python (clean).
Browser (Firefox/Playwright, vintage 2024, Median gross rent, 1440x900 and Pixel 7 size): before on the live site,
Tuscaloosa County and Greene County Cities & towns draw 0 towns; after, 12 and 5 towns in distinct shades. Tuscaloosa
ZIPs (15 shaded, 5 no-data) and Alabama counties (67 shaded) are the same before and after.

## Verdict
approve. Merge once the required checks are green on the head commit.
