---
pr: 1268
branch: fix/1264-compact-dumbbell
title: "fix(stories): compact dumbbell rows on phones, with values over the dots and no axis"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): compact dumbbell rows on phones, with values over the dots and no axis

## Summary
This PR closes #1264, the owner's 2026-11-27 request for a compact dumbbell format on mobile.

At a chart width under 560px, `DumbbellRows` (used by both the places dumbbell and the Concerns dumbbell) now draws each row on two lines:
- Line 1: the label, wrapped to at most two lines, with the change right-aligned in the accent or warning colour.
- Line 2: a light track with the dots joined by an accent segment, and each value printed above its dot.

On phones there are no gridlines, axis ticks or % scale row. The sort buttons become small pills in a single row that scrolls sideways. Label placement and collision nudging live in a pure, unit-tested module. The motion from #1228 is kept, the value labels fade in as their dots land, and reduced motion draws the final state. Desktop is unchanged.

## Scope of Change
- Files changed: 7 in `web_app` and `web_docs`, plus this review file.
- Areas touched: web_app (`DumbbellRows`, `DumbbellChart`, `ConcernsDumbbell`, `storyCharts.css`, new `utils/dumbbellLabels.ts` and its test) and web_docs.
- Commits:
  - 17b2c65b fix(stories): compact dumbbell rows on phones, with values over the dots and no axis
  - 7a7cfa48 docs(pr-1268): auto-write rubric review (bot; superseded by this file)
  - e0c00a2c refactor(stories): plan the compact dumbbell layout only on phones (#1264)

## CI Status
- 17b2c65b: CI - Build & Test and PR conventions passed.
- 7a7cfa48 (the bot commit): `action_required`, because workflows the bot triggers wait for approval.
- This push re-runs CI on e0c00a2c and this review file.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets / credentials: clean.
- Fabricated data: clean. The labels print the same real shares (`pctLabel(r.a)`, `pctLabel(r.b)`) as the tooltips and the data table. No numbers were added.
- Personal data: none.
- Destructive data changes: none. No data, API or route changes.

## Strengths
- Label placement is a pure function with 12 tests covering:
  - centring and clamping at the edges;
  - symmetric nudging in the dots' order;
  - equal values;
  - sliding inward at an edge;
  - the below-the-track fallback;
  - single values;
  - wrapping.
- Rows keep a single height (64px, 72px when a label wraps, +12px when a value goes below), so a re-sort still slides the rows cleanly.
- The pill CSS is scoped to `.sc-chips` and applies at 640px and below. `:has(> .sc-chips)` leaves the other `.sc-controls` (unit matrix, timeline) untouched.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important)
1. **Breakpoint widened, intended.** The phone layout now starts below 560px instead of the old 460px stacked breakpoint. Widths of 460–560px therefore get compact rows instead of the desktop layout. This matches the timeline's compact breakpoint and the owner's "≤ 640px or the existing breakpoint". No change made.
2. **Checked: no fallback needed.** The reviewer flagged that `--violet-ink` is defined only in `home-place.css`. It is also defined in `styles/folio.css:20`, the token sheet every story page uses, and `.sc-delta-up` already depends on it. No change.

### 🔵 Nit (Minor)
1. **Fixed in e0c00a2c.** The compact `plan` (`wrapLabel` / `placeValueLabels`) was computed on desktop too. It is now computed only when compact, with a note that the label widths are estimates.
2. **Kept as is, by design.** The compact single-value stem uses the accent tone, not the neutral `sc-stem`: the owner asked for an accent segment on the track. Desktop still uses `sc-stem`.
3. **Kept as is.** `ticks` and `tickShown` are still computed in compact mode. It is cheap.
4. **Kept as is.** Label widths are estimates (about 6.9px per character for the label, about 7.5px for the change). The real labels fit with room to spare (see Verification).

## Verification
- `npx tsc --noEmit` is clean, and `npx vitest run` passes 78 files and 729 tests. `npm run build` passes.
- Playwright Firefox against this branch's Vite (proxied to the local API on :8001), at rest. Headless Chromium here stops drawing frames after a machine restart.

  | Chart | Device | Rows | Labels overlapping | Labels hidden |
  | --- | --- | --- | --- | --- |
  | Concerns `?state=GA` | Pixel 7 | 7 | 0 | 0 |
  | Concerns `?state=GA` | iPhone 13 | 7 | 0 | 0 |
  | Concerns national (single value per row) | Pixel 7 | 7 | 0 | 0 |
  | Overview national | Pixel 7 | 12 | 0 | 0 |
  | Overview national | iPhone 13 | 12 | 0 | 0 |
  | Concerns `?state=GA` | 1440x900 | 7 | desktop layout, unchanged | — |

  - Labels overlapping is the number of rows whose value labels' boxes overlap. Labels hidden is the number of value labels below opacity 1.
  - The pairs that nearly coincide (Traffic 30.5% vs 28.7%, Land and property 19.0% vs 18.4%) are nudged apart.
  - The reduced-motion run draws the final state.
  - Mid-entrance frames show the dots sliding and the labels fading in.

## Verdict
**approve-with-nits.** Nothing blocking. The one actionable nit is fixed, and the other findings were checked and kept on purpose.
