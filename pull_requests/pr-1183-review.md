---
pr: 1183
branch: fix/1154-county-meetings-button
title: "fix(web): add Open meetings button to census county popups"
author: claude-code (for jcbowyer)
reviewed_at: 2026-11-27
reviewer: coordinator (self-review by the author session; refines the automated heuristic review)
verdict: approve-with-nits
---

# PR Review: fix(web): add Open meetings button to census county popups

## Summary
County popups on the census map now get an "Open meetings →" button, but only when the meetings API reports documents for the 5-digit county FIPS. The target was checked against the local warehouse: 25 counties have documents, other counties return 200 with 0, and Connecticut has none. So the button is gated on `meeting_count > 0`, and Connecticut planning regions get no slot. Tests and `tsc` pass. The popup fill on `popupopen` was not exercised in a browser, which is the main residual risk. This is a self-review by the author session, so it is weaker than an independent one.

## Scope of Change
- Files changed: 3 (web_app only)
- Areas touched: web_app
- Commits: af7fb8e fix(web): add Open meetings button to census county popups
- Range reviewed: `f153932..af7fb8e`

## CI Status
| Check | Status |
|---|---|
| Required checks on head commit | Not read when this was written; check the PR's Checks tab |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. No counts or county lists are hard-coded; the button depends on the live API count, and a failed lookup shows nothing.
- Personal data: clean.
- Privacy and data ethics: clean (public meeting records only).
- Destructive or bulky data changes: clean.

## Strengths
- Test written first; covers county FIPS, rejected ids, slot, fill and no-fill.
- No dead links: counties without documents and Connecticut gaps show no button.
- Slot id is only ever 5 or 7 digits, so interpolating it into the attribute is safe.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `web_app/src/pages/CensusMapPage.tsx` (county popup): the button is a plain anchor, so it reloads the page, as on the Places and place popups (same nit as in the #1150 review). Fixing it belongs with all popups at once.
- A county with documents shows its button a moment after the popup opens (one request per county, cached for the session). Acceptable, but the popup height changes after open; `keepInView` should re-pan, not verified.
- Not covered: Tuscaloosa County (01125) has 0 rows under its county id; its documents are probably filed under the city's 7-digit id. Users may expect a button there. A follow-up decision is needed on whether a county popup should also point at its places' meetings.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first, branch name, `Closes #1154` | Pass | Decisions and heatmap buttons are tracked in #1158 |
| No Fabricated Data | Pass | Button depends on a real count |
| Scope label matches filter | N/A | |
| Tests | Pass | Regression cases added |
| Docs | Not done | No governed doc page covers map popup behavior; none added |

## Test Coverage
`npx vitest run src/lib`: 104 passed. `npx tsc --noEmit`: clean. Not run: the app in a browser, and the API against the warehouse by this session (the 01033, 01125 and 09110 results came from a read-only check run on the owner's machine).

## Verdict
approve-with-nits. Nothing blocks; confirm the popup in a browser (open Colbert County, AL, which has 72 documents, and a county without any) before relying on it.
