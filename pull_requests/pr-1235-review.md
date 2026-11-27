---
pr: 1235
branch: fix/1228-chart-motion
title: "fix(stories): Concerns dumbbell draws on phones, and story charts get the reference's motion"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): Concerns dumbbell draws on phones, and story charts get the reference's motion

## Summary
This PR closes #1228.

On a phone, the Concerns dumbbell drew one row with no dots: every dot stayed at opacity 0 and every line at scaleX(0). The cause is the snap layout. Each phone story screen is a fixed-height section whose `.stance-grid` scrolls on its own, and the 370px chart showed only its first row inside it. `DumbbellRows` revealed only after an `IntersectionObserver` with `threshold: 0.2` saw a fifth of the chart, and it had no fallback. `UnitMatrixChart` had the same gate at `0.15`.

The PR adds `useChartReveal`, a shared hook:
- It reveals on any visible pixel (threshold 0).
- If the chart has sat in the window for 1.8 s without the observer firing, it draws the final state.
- Under `prefers-reduced-motion` it always draws the final state.
- A new replay key (a new scope or series) replays the entrance.

It also ports the motion from vizjb12 §4.1, §4.3 and §4.5 to the dumbbell, the timeline and the unit matrix, using CSS transitions only. The stacked dumbbell layout is fixed: the label and a right-aligned change share one line, and the gridlines are short per-row segments, so nothing crosses a label.

The reviewer found one Important issue: a replay showed the final state for a frame, then played an exit animation. That is fixed in b444fbbe.

## Scope of Change
- Files changed: 8 in `web_app` and `web_docs` (+232 / −71 against `origin/main`), plus this review file.
- Areas touched: web_app (story chart components and CSS), web_docs.
- Commits:
  - f1cb4168 fix(stories): Concerns dumbbell draws on phones, and story charts get the reference's motion
  - b444fbbe fix(stories): a chart replay hides in the same render, so it never flashes the final state first (#1228)
  - 23449eb6, f58406dc docs(pr-1235): auto-write rubric review (bot; superseded by this file)
  - merge commits from origin/main (#1223's tick picker kept in `DumbbellRows` and `TimelineChart`, #1226)

## CI Status
CI - Build & Test and PR conventions passed on b444fbbe. The bot's review commits show `action_required`, because workflows triggered by the bot wait for approval. This review commit re-runs CI.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets / credentials: clean.
- Fabricated data: clean. No new numbers; every value drawn comes from the same API fields as before. Only the motion and layout changed.
- Personal data: none touched.
- Destructive data changes: none. No data, API or route changes.

## Strengths
- The root cause is found and fixed at the trigger, not worked around with a larger threshold. The fallback means a chart can't be left invisible, even where the observer can't see past a clipping ancestor.
- Reduced motion is covered at every level: the hook returns revealed, the inline delays are skipped, and the CSS media query turns off every transition and animation.
- Transition delays are set per property, in the same order as the CSS `transition` lists:
  - `.sc-pt` and `.sc-ms-pop`: opacity, transform, fill. A milestone selection's colour change is never delayed.
  - `.sc-sq`: transform, fill, opacity. The diagonal wave delays only the fade-in, and regrouping keeps its reading-order flight.
- Hooks are called before every early return. The rAF, observer and interval are all cleaned up.
- The `revealDelayMs` helper is pure and unit-tested.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important)
1. **Fixed in b444fbbe.** A replay (Timeline mode toggle, matrix scope change) set `revealed=false` in an effect, after the new elements had already painted fully revealed. They then animated out before replaying.
   - The hook now stores the key it was revealed for and compares it during render (`useChartReveal.ts`).
   - The dumbbells were not affected, because they remount by `key`.

### 🔵 Nit (Minor)
1. **Fixed in b444fbbe.** The fallback poll ran every 300 ms per unrevealed chart, including in hidden tabs. It now runs every 500 ms and skips `document.hidden`.
2. **Fixed in b444fbbe.** `.sc-label-halo` was unused after the stacked-layout change and is removed.
3. **Left as is.** At 280px, a very long label and its change share one line with no truncation. The real concern labels ("Land and property", "Electricity costs") and the town names fit at 318–340px, as the Playwright checks below show. Worth revisiting if longer labels appear.
4. **Left as is.** Timeline points are tabbable while hidden, before the reveal. The window is brief and ends at the reveal or the 1.8 s fallback.
5. **Left as is, by design.** Rows added by "Show all" mount already revealed, so they appear with no entrance.

## Verification
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 75 files and 700 tests passed after merging origin/main.
- `npm run build` (web_app): passes.
- `npm run build` (web_docs): `[SUCCESS] Generated static files`.
- Playwright on this branch's Vite (proxied to the local API on :8001), before the machine restart, on the Concerns screen:
  - Pixel 7, iPhone 13 and 1440x900, each at `?state=AL`, `?state=GA` and national. At rest, all rows are drawn (6, 7 and 7) with every dot at computed opacity 1, and the changes are right-aligned at x = chart width.
  - Mid-animation frames, with CDP playback slowed to 0.1, show the staggered dot ride and line growth.
  - A short-viewport run (412x660, chart below the inner fold) ends fully drawn through the fallback.
  - The reduced-motion run draws the final state at once.
  - The Overview places dumbbell is fully drawn at all three sizes, national (12 rows) and Alabama (3 rows).
  - The Meetings timeline on a phone shows the line, points, end value and milestone list at rest.
- Not completed:
  - A visual desktop screenshot of the Meetings timeline. In pinned mode, the instant scroll leaves the story's own scroll-scrubbed screen (`.stance-right` opacity) unrevealed. That is the story's mechanism, not the chart's: the chart's own marks were revealed.
  - Re-checking after b444fbbe. After the restart, headless Chromium stopped producing frames for any page here, the live site included, so screenshots timed out.

## Verdict
**approve-with-nits.** Nothing blocking. The one Important finding is fixed, and the remaining nits are minor.
