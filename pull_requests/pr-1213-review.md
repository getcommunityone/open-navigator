---
pr: 1213
branch: feat/1195-drill-box-morph
title: "feat(stories): boxes reorganize into the county map on the state drill-down"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: boxes reorganize into the county map on the state drill-down

## Summary
This PR animates the Data Center Story Overview's state drill-down (#1195). The state's national boxes lift, then fly and re-form into its county box grid while the other states fade and drift outward. **United States** plays the plan in reverse, and a click on the home map plays it on arrival. The transition is drawn on a canvas overlay, and its final frame is read from the real county SVG, so no box stands for anything it doesn't. Reduced motion swaps the maps instantly. A click or key press ends the transition at once, and focus and keyboard navigation are untouched.

The reviewer found nothing Critical. It raised two Important issues: a failed meeting-mentions fetch held the map hidden for 10 s, and the canvas was sized to the whole wrapper. Both are fixed in this PR's follow-up commit, together with two of the Minor items. Verdict: approve with nits.

## Scope of Change
- Files changed: 12, plus this review (+842 / -65 before the review fixes). Only web_app and web_docs are touched.
- Areas touched:
  - web_app: `utils/boxMorph.ts` with its test; `stance/MapDrill.tsx`, `nationalDots.ts`, `drillState.ts`; `StoryDotMap`, `StoryCountyMap`, `StoryScreenView`, `home/StoryStatesMap`; `stance.css`.
  - web_docs: `guides/data-stories.md` and `development/story-drill-box-transition.md`.
- Commits:
  - 72f765c3 feat(stories): boxes reorganize into the county map on the state drill-down
  - 3d9666be merge of origin/main (conflict in StoryScreenView with #1199's dumbbell, resolved by keeping both)
  - 86f7a5c4 docs(pr-1213): auto-write rubric review (bot)
  - the review-fix commit that adds this file
- Range reviewed: `origin/main...HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | see PR checks on the head commit |
| Documentation Build | see PR checks on the head commit |
| Backend Tests | see PR checks on the head commit |
| API Types | see PR checks on the head commit |
| PR conventions | passed on 3d9666be |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. No numbers are added. Every landed box is read from the rendered county SVG (`circle[data-box]`: place, radius, fill and opacity). National colours come from the same real `by_state` counts through the shared `nationalPaint`. Spawned and faded boxes are transitional only.
- **Personal data:** clean. Nothing is stored. The navigation flag is `{ drillFrom: 'national' }`.
- **Destructive data changes:** none.

## Strengths
- The layout math is pure (`planDrillMorph`, `sampleStep`, `sampleAt`). There are 11 tests, covering more and fewer boxes, no parent box, exact start and end, reverse, drift, stagger and total time, and lift.
- The end state comes from the real map by construction, so the animation can't drift from the county colours.
- The real SVG stays mounted, only made transparent. This keeps the accessibility tree, focus and keyboard navigation intact. There is no new dependency.
- The design note records the decisions and limits.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **A failed meeting-mentions fetch held the map hidden for 10 s.** `StoryScreenView.tsx` passed `county='loading'` whenever `byPlace == null`, including after an error. The job then waited `WAIT_MS` with the SVG transparent. The reviewer traced this through `useStoryData`, which leaves the data undefined and sets status `error`. **Fixed:** `county` is `'none'` when `p.status['meeting-mentions'] === 'error'`, and the run finishes at once.
2. **The canvas was sized to the whole wrapper.** That covers the dumbbell and the counts, which on a high-DPR phone is a large bitmap cleared every frame. The reviewer found this from `size()` using `wrap.clientHeight`. **Fixed:** the canvas height follows the boxes' extent and only grows during a run, so it isn't reallocated each frame.

### 🔵 Nits / suggestions (Minor)
3. **A stale `pending` snapshot could be used by a later scope change from elsewhere.** **Fixed:** a snapshot is used only within 2 s of the pick.
4. **The run effect depended on `clearArrival`, and through it on `navigate`'s identity.** **Fixed:** it is read through a ref, so a new `navigate` can't restart a running transition.
5. **Possible single blank frame (open).** The scope-change decision runs in `useEffect`, so one frame can paint without the canvas drawn. This wasn't visible in the captured frames. It could move to `useLayoutEffect`.
6. **Out animation plays only from the map (open, documented in the PR).** Broadening via the scope chip or "All of AL" doesn't call `beforePick`, so the out animation plays only from the map's own controls.
7. **Arrival flag can survive when the story opens on another screen (open).** If the story opens on a screen other than the Overview, the arrival flag stays in history until the Overview mounts. This is harmless.
8. **Per-frame allocation and colour parsing (open).** Cost is acceptable over about 1 s. Colours could be pre-parsed in the plan.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1195 has all four parts; branch `feat/1195-drill-box-morph`; `Closes #1195` |
| Conventional Commits | Yes | Co-author trailer on the feature commits (the merge commit uses git's default message) |
| No fabricated data | Yes | See scans |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | Yes | The URL stays the authority; the arrival flag is navigation state, cleared after use; label and data unchanged |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | Guide section and design note, kebab-case with frontmatter |
| Telemetry and logging | n/a | No new API |
| Tests | Yes | boxMorph vitest cases; behaviour checked in Playwright |
| Shared libraries | n/a | |

## Test Coverage
- `npx tsc --noEmit` passes. `npx vitest run`: 67 files, 619 tests pass. `npm run build` passes. The docs build passes.
- Playwright against this branch's dev server, at 1440×900 and on an iPhone 13. Frames were taken at the click and at 250, 500, 800 and 1200 ms on `page.clock`.
  - The final county map matches the reduced-motion run: 4,188 boxes, 5 colours, same legend.
  - Under reduced motion it swaps instantly.
  - Reverse plays back to the national map.
  - A click during the transition ends it.
  - ArrowRight still drives the county readout.
  - Arrival from the home map plays, and the history state is cleared.
  - All of this was re-run after the review fixes.
- `e2e/story-nav.check.mjs` timed out at different panels on both this branch and an `origin/main` baseline on the same loaded machine, so the result is inconclusive. It isn't affected by this change, which touches only the Overview map wrapper.

## Verdict
**approve-with-nits.** The Important findings are fixed. The remaining items are minor and optional.
