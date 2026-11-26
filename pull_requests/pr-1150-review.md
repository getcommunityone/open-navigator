---
pr: 1150
branch: fix/1149-places-popup-drilldown
title: "fix(web): Places map popup stays in view and offers an Open meetings button"
author: claude (agent session)
reviewed_at: 2026-11-26
reviewer: coordinator only (the author reviewed its own change; no independent reviewer ran)
verdict: approve-with-nits
---

# PR Review: fix(web): Places map popup stays in view and offers an Open meetings button

## Summary
Moves the Places map popup into `web_app/src/lib/placePopup.ts`, gives it a button ("Open meetings →" for a place,
"Browse places in {state} →" for a state), escapes the place name, and sets Leaflet auto-pan padding so the popup has
room on every side. Every "Done when" line in #1149 has a test or a code line behind it. The review was written by the
same session that wrote the change, so treat it as a self-check; no blocking findings. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 3 (+107 / -23)
- Areas touched: web_app
- Commits: e038423 fix(web): Places map popup stays in view and offers an Open meetings button
- Range reviewed: `bc27a71..e038423` (main has since moved to `0ecc081`; it does not touch these three files)

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | Not read when this was written; check the PR's Checks tab before merging |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. The popup shows `transcript_count` and `place_count` from the warehouse pin; nothing is hard-coded.
- Personal data: clean.
- Destructive or bulky data changes: clean.

## Strengths
- The popup logic is a pure function, so label, href and escaping are unit-tested without a map.
- Fixes a real injection path: `pin.name` was interpolated into HTML unescaped.
- Test written first; the old inline builder had no test.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `web_app/src/lib/placePopup.ts` (the `<a href>`): a plain anchor inside Leaflet HTML does a full page load, not a client-side route change. Unchanged from the old "View →" link, so not a regression. A click handler using the router would avoid the reload.
- `PLACE_POPUP_OPTIONS`: `keepInView: true` and `autoPan: true` overlap in effect. Both are kept deliberately so a pan that drags the popup off-screen pulls the map back. Not verified in a browser.
- The 90px top padding is sized for the page header by eye; if the header height changes, this number must change with it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1149 has Problem, Done when, Contract, Read first; branch `fix/1149-places-popup-drilldown`; PR says `Closes #1149` |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | Scan above |
| New Python in `packages/` | n/a | No Python |
| Scope label matches filter | n/a | The state button carries `?state=`; the Places page already reads it and shows its label |
| Docs | n/a | No docs added |
| Tests | Yes | `placePopup.test.ts`, 6 tests; the escaping test fails on the old builder |

## Test Coverage
- Run locally: `npx vitest run src/lib/placePopup.test.ts` (6 passed), `npx tsc --noEmit` (clean).
- Not run: `npm run build`, the full vitest suite, and any check in a real browser. The auto-pan behaviour is configuration passed to Leaflet and is only asserted as options, not observed.

## Verdict
approve-with-nits. Before merging: read CI on the latest commit and look at a popup near the map edge in a browser once.
