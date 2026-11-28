---
pr: 1482
issue: 1446
branch: feat/1446-who-governs-ui
title: "feat(web): Who governs and Officials heard most recently on the place page, body page"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1482 review

Reviewed against `.claude/review-rubric.md`.

## Summary

Adds "Who governs <place>" and "Officials heard most recently" to the place home and a `/bodies/:bodyId` page, all
from the #1445 endpoints, plus the coverage report. Checked in a real browser at Pixel 7 and 1440 against a branch API
(Playwright script in `web_app/e2e/who-governs.check.mjs`); vitest and tsc pass. Approve with nits.

## Scans

- Secrets: clean. Fabricated data: clean (no seeded numbers; "Members not on file", "No meetings on file yet" and
  explicit empty states instead). Personal data: officials only; residents never listed. Destructive changes: none.

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- The existing place page subtitle still shows the geoid ("0177256") because the meeting-documents response has no
  place name; the new section headings name the place correctly. Small follow-up to read the name from the bodies
  response.
- Play links open YouTube in a new tab rather than the in-app player; matches the jump-to-moment ask, could reuse
  `MeetingPlayer` later.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Scope label matches the filter | Yes | headings name the place in the URL; body page shows its place and links back |
| No fabricated data | Yes | empty states, no fallback numbers |
| Phone-first, PageClose | Yes | 44px targets; Close from Layout (`showsPageClose`) |
| React telemetry | Yes | `withSpan` on both loads |
| Docs with the change | Yes | decision page: API, UI, coverage |

## Test Coverage

vitest 1,071 passed (10 new), tsc clean, Playwright check all ok at Pixel 7 and 1440.

## Verdict

approve-with-nits.
