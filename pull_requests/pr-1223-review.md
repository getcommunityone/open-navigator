---
pr: 1223
branch: fix/1222-phone-axis-map-button
title: "fix(stories): year labels fit a phone and the map card's button opens the state (#1222)"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): year labels fit a phone and the map card's button opens the state (#1222)

## Summary
The PR fixes the owner's two phone bugs on topic stories.
- **Year axis.** Labels are now picked by the room they have (`utils/axisTicks.ts`), so 2016–2026 no longer runs together at 412px. The dumbbell's % axis uses the same rule.
- **Map card button.** The root cause was the map svg taking focus on a tap. `useMapKeyboard.onFocus` then picked the page's own state, so on touch the card always showed that state, and its button linked to the current page.
- **Card behaviour now.** Pointer focus no longer picks a state. A touch tap shows the tapped state's card, the button navigates, and a card for the current page says "You're reading the [State] story".

Verified in Playwright at Pixel 7, iPhone 13 and 1440×900, and on the home page map. The reviewer's one Important finding (a stuck pointer flag) was fixed in 71f2b2f3. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 12 (+294 / -73, excluding this review file)
- Areas touched: web_app, web_docs
- Commits:
  - e1ee21da fix(stories): year labels fit a phone and the map card's button opens the state (#1222)
  - a0b9591f docs(pr-1223): auto-write rubric review [skip review] (bot; superseded by this file)
  - 71f2b2f3 fix(stories): a press that focuses nothing no longer skips the map's keyboard start; Enter on the current state stays put (#1222)
  - merge commits from the branch and origin/main
- Range reviewed: `0589f029..9a4f51c4`

## CI Status
| Check | Status |
|---|---|
| PR conventions (linked issue) | pass |
| Documentation Build (Docusaurus) | pass |
| Frontend Build (TypeScript + Vite) | read before merge (see the PR's checks) |
| Backend Tests (Python) | read before merge (no Python touched) |
| API Types (OpenAPI -> TypeScript) | read before merge (no API touched) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean (pre-commit secret hooks passed; no credentials in the diff).
- Fabricated data: clean. There are no numbers in served paths. The 800 ms pointer window and the axis label metrics are layout constants, not data.
- Personal data: clean. Nothing is stored or logged.
- Destructive data changes: none.

## Strengths
- The root cause was reproduced read-only on the live site before any fix. Tapping Texas from `?state=AL` moved the page to Texas while the card still offered "Open the Alabama story".
- The tick picker is a pure function, with a width sweep test (280–1200px, 2–30 years) that asserts no overlap.
- The keyboard start (#1146) is preserved and covered by a unit test. Other maps using `useMapKeyboard` (StoryDotMap, StoryCountyMap) only lose the accidental focus-on-click pre-selection.
- The docs record the change in behaviour and its reason in `web_docs/docs/guides/data-stories.md`.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None open.
- Fixed in 71f2b2f3: `hooks/useMapKeyboard.tsx`. The boolean pointer flag stayed set after a press that focused nothing (a press on an already-focused map, or a cancelled touch), which skipped the next keyboard focus's start. Verified by tracing. It is now a timestamp with `POINTER_FOCUS_MS`, and a regression test covers "press, no focus, later keyboard focus".

### 🔵 Nits / suggestions (Minor)
- Fixed in 71f2b2f3: `components/home/StoryStatesMap.tsx`. Enter on the current page's state re-navigated to the same URL, replaying the drill-down transition. It is now guarded by `isCurrentPage`.
- `StoryStatesMap.tsx`, `onBox`. A touch tap on the page's own state when that state has no quote card only sets the hover stroke. The page is already that state's story, so nothing is lost. Left as is.
- `StoryStatesMap.tsx`, `onBox`. A second tap on another box of the same state navigates rather than cycling to another quote. This follows the issue's design: the second tap opens, and #1120 is kept. Revisit if readers want to browse a state's quotes on a phone.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1222 has all four parts; branch `fix/1222-…`; `Closes #1222` |
| Conventional Commits | yes | co-author trailer on both agent commits |
| No fabricated data | yes | scan clean |
| New Python in packages/ | n/a | no Python |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | yes | the button navigates via `?state=`; label, highlight, select and charts change together (Playwright) |
| Match evidence on filtered tiles | n/a | |
| Docs | yes | `web_docs/docs/guides/data-stories.md` |
| Telemetry and logging | n/a | |
| Tests | yes | axisTicks, currentPage and useMapKeyboard pointer focus; each would fail before the fix |
| Shared libraries | n/a | |

## Test Coverage
Run locally on the branch:
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 74 files, 693 tests.
- `npm run build` (web_app) and the docs build: both pass.

Playwright against a local Vite (proxied to the API on :8001) at Pixel 7, iPhone 13 and 1440×900:
- Texas on `?state=AL` shows the "Open the Texas story" card, and the button goes to `?state=TX`. The heading, the select and the charts all show Texas.
- On Pixel 7, tapping Alabama on `?state=AL` shows "You're reading the Alabama story".
- On the home page (Pixel 7), the Texas card's button goes to `/stories/data-centers?state=TX`.

Axis screenshots: before on the live site the labels overlap; after, 2016, 2018 … 2026.

Not covered: a component-level test of the touch two-step (the repo has no DOM testing library). It is covered by Playwright instead.

## Verdict
approve-with-nits. Nothing blocking. Merge once the required CI is green.
