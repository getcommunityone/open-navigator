---
pr: 1156
branch: fix/1154-map-popups-drilldown
title: "fix(web): decisions, census and heatmap popups stay in view; census names escaped"
author: claude (agent session)
reviewed_at: 2026-11-26
reviewer: coordinator only (the author reviewed its own change; no independent reviewer ran)
verdict: approve-with-nits
---

# PR Review: fix(web): decisions, census and heatmap popups stay in view; census names escaped

## Summary
Moves the auto-pan padding from #1150 into `web_app/src/lib/mapPopup.ts` and applies it to the decisions, heatmap and
census map popups, and escapes the name the census popups write into HTML. It is one part of #1154 (`Refs`, not
`Closes`): the buttons are deliberately left out because the decisions popup is display-only by design, heatmap records
have no place id, and the census place target is unconfirmed. No blocking findings. This review was written by the same
session that wrote the change, so treat it as a self-check.

## Scope of Change
- Files changed: 6 (+~60 / -~20)
- Areas touched: web_app
- Commits: one, `fix(web): decisions, census and heatmap popups stay in view; census names escaped`
- Range reviewed: `8844398..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | Not read when this was written; check the PR's Checks tab before merging |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean: no credentials, no figures added, no personal data, no data changes.

## Strengths
- The padding is defined once, and a test asserts the Places popup builds on it.
- Leaves out buttons it cannot back with a real destination, rather than guessing a link (decisions would 404).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `CensusMapPage.tsx` is a very large file; the two `bindPopup` edits were made by string match, so a third `bindPopup` elsewhere in it would be missed. A grep found only the two.
- The popups are only checked as settings passed to Leaflet; no browser check of auto-pan was done.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1154 with all four parts and a dated note on what changed; branch `fix/1154-...`; `Refs #1154` |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | Nothing displayed is added |
| Tests | Yes | `mapPopup.test.ts` (3 tests) written first; `placePopup.test.ts` still passes (9 total) |
| Docs with the change | n/a | No behaviour, contract or data-grain change beyond popup placement |

## Test Coverage
Run locally: the two vitest files (9 passed); `tsc --noEmit` has 0 errors in touched files (other errors come from
packages missing in the local `node_modules`). Not run: `npm run build`, the full suite, a browser.

## Verdict
approve-with-nits. Before merging: read CI on the latest commit.
