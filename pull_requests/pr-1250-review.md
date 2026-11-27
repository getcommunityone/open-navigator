---
pr: 1250
branch: fix/1229-map-taps-check
title: "fix(stories): story map cards open and close on a tap, never on hover (#1229)"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent (frontend-specialist) and coordinator; supersedes the github-actions auto-reviews of b7039d2d and af612b4a
verdict: approve-with-nits
---

# PR Review: story map cards open and close on a tap, never on hover

## Summary
The owner reported that on a phone, after tapping one state on the live topic story map, no other state could be tapped. The cause is in the deployed build. The first tap focused the map's svg. `useMapKeyboard`'s `onFocus` treated that as keyboard focus and showed the page's own state (Alabama). On touch nothing ever replaced that card, so each later tap opened another state's story in place while the Alabama card stayed pinned. This was reproduced on the live site with Playwright at Pixel 7. #1223, already on `main`, stopped pointer focus from picking the starting state.

This PR finishes the owner's follow-up rule on all three story maps: on touch, nothing depends on hover.
- A tap opens a card.
- The card closes on a 44px Close button or a tap outside the map. Scrolling doesn't close it.
- On the Overview dot map, the first tap shows the card instead of narrowing at once.
- Desktop hover and the #1146 keyboard path are unchanged.
- The missing multi-tap e2e check is added; it passes 107 of 107 locally.

The reviewer found no Critical issues, 1 Important and 8 Minor. The Important one and 5 Minor ones are fixed in 5eb99c92. One Minor is follow-up #1252, and the other 2 are accepted with reasons below.

## Scope of Change
- Files changed: 7 (+528 / -16, excluding this review file); 358 of the added lines are the new e2e check
- Areas touched: web_app, web_docs
- Commits:
  - 975aa5f5 fix(stories): story map cards open and close on a tap, never on hover (#1229)
  - 5eb99c92 fix(stories): review fixes for the map tap rules (#1229)
  - plus merges of origin/main (a docs conflict in `data-stories.md` with #1230's section, resolved by keeping both) and of the bot's auto-review commits
- Range reviewed: `e2ec61c5..HEAD` (feature commits only)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pending when this was written; merge waits for green |
| Documentation Build | pending; the local `npm run build` in `web_docs` passed |
| Backend Tests | pending; no Python changed |
| API Types | pending; no API changed |
| PR conventions | pending |
| Docker Build Test | not required (no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. No numbers are added. The cards still show the passages and counts the API serves. The e2e check only reads the page and asserts nothing about values.
- **Personal data:** clean. Nothing is stored or logged. The outside-tap listener reads only the event target.
- **Privacy and data ethics:** clean. No person data, no scraping, no contact.
- **Destructive data changes:** none.

## Strengths
- One mechanism covers all three maps: a capture-phase document listener in the shared hook. It is scoped to the stage that holds both the svg and the card. Card buttons sit inside the stage, so a card never closes before its button's click fires. The reviewer checked this, and the e2e Close-button step covers it.
- The owner's bug now has a regression check that would have failed on the deployed build. It taps A, B, C, B, A, D and asserts that the card and outline follow each tap.
- `data-state` on the boxes and dots gives tests a stable hook without any visible change.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **e2e false pass on the dot map** (`web_app/e2e/map-taps.check.mjs`, `dotMap`).
   - Problem: when a tapped state had no passage, the story narrowed at once. The script logged one `ok`, returned, and exited 0 without running the Close, outside-tap, second-tap and county checks.
   - Verified by reading the code.
   - **Fixed in 5eb99c92:** this path is now a FAIL that names the checks that didn't run.

### 🔵 Nits / suggestions (Minor)
1. **Weak desktop Enter assertion.** It only checked that the URL left `state=AL`.
   - **Fixed:** it now asserts that the URL holds the state the arrows reached.
   - It also adds a click-outside check for a card opened from the keyboard.
2. **Close button located page-wide** (`.map-card-close:visible` then `.first()`).
   - **Fixed:** the button is now found inside the visible map's own stage.
3. **Stale `move` in the effect** (`useMapKeyboard.tsx`). Safe with today's callers, but fragile.
   - **Fixed:** the listener calls the latest `setActive` through a ref, and the `eslint-disable` is gone.
4. **Close button accessibility.** The label was a bare "Close", and focus fell to `body`.
   - **Fixed:** the button is named "Close the [State/County] card", and focus returns to the map.
   - That focus is marked as a pointer focus, so `onFocus` doesn't reopen the page's own state. The e2e check confirms that Close leaves no card.
5. **Scroll gestures closed the card** (the listener ran on `pointerdown`).
   - **Fixed:** it now runs on `pointerup`. A touch that becomes a scroll ends in `pointercancel`, so scrolling to read a tall card leaves it open.
6. **Hybrid devices.** `isTouchOnly()` reads `(hover: none)`, so a finger on a touch laptop or an iPad with a trackpad still acts like a mouse.
   - **Follow-up #1252** (action-item): key the touch rules off `PointerEvent.pointerType`.
7. **A card with no close path if `passage` ever stops following `hover`** (`StoryDotMap`).
   - That can't happen today, because both come from `hoverCode`.
   - Accepted. Any change that shows a card at rest would also need the outside listener.
8. **Second tap on the current page's state** does nothing visible (`isCurrentPage`).
   - This is by design from #1223, and the card says "You're reading the [State] story".
   - Accepted.

Left as is: the `outlined` probe reads the box stroke colour (`#1c1917`). If a theme change breaks it, the check fails loudly; it can't pass falsely.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/1229-map-taps-check`, `Closes #1229`. The issue has all four parts, plus a dated scope line for the owner's touch rule |
| Conventional Commits | Yes | Both feature commits are `fix(stories): …` with the co-author trailer |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | n/a | No Python |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | Yes | Picking a state still goes through `onPickState` or the story href, so the label, URL and query move together. Showing a card without a pick doesn't change scope |
| Match evidence on filtered tiles | n/a | Card quotes unchanged |
| Docs | Yes | `web_docs/docs/guides/data-stories.md`, "Changed 26 Nov 2026 (#1229)" |
| Telemetry and logging | n/a | |
| Tests | Yes | Unit tests for `pressedOutside` and `close`; the e2e multi-tap check covers the owner's bug |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 75 files, 707 passed, 1 skipped, after merging origin/main.
- `npm run build` (web_app) and the Docusaurus build: pass.
- `node e2e/map-taps.check.mjs --base http://localhost:5287`: 107 of 107 ok. It ran against a local Vite on this branch, proxied to the local API, at:
  - Pixel 7 and iPhone 13 on chromium: the topic story box map, the home map, the Overview dot map, and the county map after the drill.
  - 1440x900: keyboard, hover, click and click-outside.
- The same taps against the live site, before the change, reproduced the stuck Alabama card.
- Not covered: real WebKit (only chromium is installed) and hybrid hover-plus-touch devices (#1252).

## Verdict
Approve with nits. The Important finding and five of the Minor ones are fixed on the branch, and #1252 tracks hybrid devices. Merge once the required CI checks are green on the head commit.
