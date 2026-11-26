---
pr: 1161
branch: fix/1154-census-place-meetings
title: "feat(web): census place popups get an Open meetings button"
author: claude (agent session)
reviewed_at: 2026-11-26
reviewer: coordinator only (the author reviewed its own change; no independent reviewer ran)
verdict: approve-with-nits
---

# PR Review: feat(web): census place popups get an Open meetings button

## Summary
Adds `meetingsButtonHtml(geoid)` to `web_app/src/lib/mapPopup.ts` and appends it to the census place popup. The target
`/jurisdiction/{geoid}/meetings` is backed by the meetings API matching `census_geoid`
(`api/routes/jurisdiction_meeting_documents.py`). A value that isn't exactly 7 digits, including the `idx_N`
placeholder, gets no button. One part of #1154 (`Refs`). No blocking findings. This is the author's own review.

## Scope of Change
- Files changed: 3 (+28 / -3)
- Areas touched: web_app
- Commits: one, `feat(web): census place popups get an Open meetings button`
- Range reviewed: `6c28a09..HEAD`

## CI Status
| Check | Status |
|---|---|
| Required checks and PR conventions | Not read when this was written; check the PR's Checks tab before merging |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean.

## Strengths
- No dead link: a placeholder or malformed id yields no button, and the tests cover those cases.
- Reuses the shared popup module from #1156.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- The link target is backed by the meetings API's SQL, not by a request: no warehouse was reachable here, so it isn't confirmed that census place GEOIDs have meeting documents. The route returns an empty 200 for an unknown id, so the failure is an empty page, not an error.
- Plain anchor, full page load (same as the earlier popups).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `Refs #1154`, issue has the four parts and a dated change note |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | The link comes from the map's own GEOID |
| Tests | Yes | New tests for the link, malformed ids and null; 100 passed in `src/lib` |

## Test Coverage
Run: `npx vitest run src/lib` (100 passed); `tsc` clean for touched files. Not run: browser, a live meetings request.

## Verdict
approve-with-nits. Before merging: read CI on the latest commit.
