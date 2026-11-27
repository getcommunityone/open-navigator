---
pr: 1254
branch: fix/1238-census-map-phone
title: "fix(data-explorer): census map works by tap on phones, keeps the map in view, and frames the whole area on desktop"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: subagent (frontend-specialist, read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(data-explorer): census map works by tap on phones, keeps the map in view, and frames the whole area on desktop

## Summary
This PR makes the Data Explorer census map (`/data-explorer/map/...`) usable on phones. A tap previews a shape, and a second
tap or an explicit button drills. The pinned card is a collapsed one-line bottom sheet that expands to at most 45% of the
window. The outline toggles move out of the map, and info panels gain a close button.

It also covers the owner's desktop request. From 1024 px the area's panel sits beside the map and stays in view. A
county's towns or ZIPs are framed as the whole county with margin, where before the view was zoomed tightly onto the towns.

The read-only reviewer's three Important findings were all verified and fixed in `3dee8171`:
- the sheet became sticky on wide touch screens;
- the Stage kept a consumed preview;
- a preview went stale when the metric changed.

Browser checks pass at Pixel 7, iPhone 13, 1100, 1366, 1440 and 1920 px. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 4 (web_app 3, web_docs 1), plus this review
- Areas touched: web_app, web_docs
- Commits:
  - e1275959 fix(data-explorer): census map works by tap on phones, keeps the map in view, and frames the whole area on desktop
  - 3dee8171 fix(data-explorer): reset the tap preview after a drill or a metric change, and keep the sheet fixed on wide touch screens
  - ffd05e10 docs(pr-1254): auto-write rubric review (bot; superseded by this file)
- Range reviewed: `origin/main...HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | see PR checks on head (local `npm run build` OK) |
| Documentation Build | see PR checks on head (local docs build OK) |
| Backend Tests / API Types | no backend change |
| PR conventions | branch `fix/1238-…`, `Closes #1238`, issue has four parts |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. The strip and sheet values come from the existing per-region display maps and show `—` when null. Real-dollar figures use the same CPI `deflate` as the card. The "Soon" items are unchanged.
- **Personal data:** clean. Nothing is stored or logged.
- **Destructive data changes:** none.

## Strengths
- Tap mode is opt-in through a Stage prop (`onTapPreview`). Without the prop the Stage behaves as before, so desktop hover and click are untouched.
- `InfoHelpTrigger` changes are additive. Every caller gains a close button, and `mobilePlacement` defaults to `anchored`.
- Dropping `backdrop-blur` from the sheet avoids making it the containing block of the fixed popover.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All of these were found by the reviewer, verified in code, and fixed in `3dee8171`:
- **`CensusDrilldownMapPage.tsx`, aside classes:** `lg:sticky` overrode the sheet's `fixed` on touch screens of 1024 px or wider. Sticky now applies only outside sheet mode.
- **`CensusDrilldownStage.tsx`:** a drill from the strip's button left the Stage's `previewId` set, so the next tap on that shape drilled immediately. The new `tapPreviewId` prop clears it.
- **Page:** a preview captured under one metric, year or mode was formatted under another. The preview is now cleared when `metricSlug`, `displayVintage` or `valueMode` changes.
- **`InfoHelpTrigger.tsx`:** the `top` placement only applied at 760 px or narrower, so it was clipped inside the sheet on wider touch screens. It now uses the same media query as sheet mode.

### 🔵 Nits / suggestions (Minor)
- A desktop window 760 px wide or narrower, used with a mouse, gets tap mode (two clicks to drill, no hover readout). This is intended per #1238, which specifies `max-width: 760px`.
- With no pin on a phone, the tapped shape appears in both the strip and the in-flow card below the legend. The two match, so the duplication is harmless.
- The aside has no `max-h` while sticky. A card taller than the window would clip at the bottom, but today's card is about 340 px.
- There is no unit test for tap mode. The web_app has no DOM test environment (no jsdom or testing-library), so the behaviour was verified in a real browser instead (below).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #1238 has all four parts; a dated contract note was added for the hook and the desktop scope |
| Conventional Commits | ✅ | Co-author trailer present |
| No fabricated data | ✅ | Scan clean |
| New Python in `packages/` | n/a | |
| dbt / naming / keys / years | n/a | UI only |
| Scope label matches filter | ✅ | The breadcrumb and URL are unchanged |
| Docs | ✅ | `web_docs/docs/guides/data-explorer-matrix-map.md` covers the map panel, phones and touch, and framing |
| Telemetry | n/a | |
| Tests | 🔵 | No DOM test environment; verified by Playwright |
| Shared libraries | ✅ | The shared `InfoHelpTrigger` change is backward compatible; other callers keep the anchored panel and gain only a close button |

## Test Coverage
Run locally:
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 75 files, 701 passed, 1 skipped.
- `npm run build`: OK. Docs build: OK.

Playwright ran on the Firefox engine, because headless Chromium on this machine would not render a frame, even for a
`data:` URL. The phone viewport and user agent came from `devices[...]` with `hasTouch`. The path tested was US →
Georgia → Greene County → Cities & towns.

| Device | Map visible, before | Map visible, after |
|---|---|---|
| Pixel 7 | 118 px | 223 px (whole map), sheet collapsed to 56 px; expanded 345 px (41%) with the map still above it |
| iPhone 13 | 0 px | 209 px, sheet 56 px; expanded 299 px (45%) with the map above it |

- The info panel closes with its button and with an outside tap.
- At 1366×768, 1440×900 and 1920×1080 the panel stays beside the map, and the whole county is visible with margin.
- At 1100×700 the panel is beside the map; before this change it was below the fold.
- Not covered: `(hover: none)` on a wide tablet could not be emulated in Firefox. The CSS path was checked by reading.

## Verdict
**approve-with-nits.** Nothing blocking remains; the nits are noted for follow-up judgement and none affect correctness.
