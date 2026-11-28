---
pr: 1404
branch: feat/1400-cross-page-box-particles
title: "feat(stories): unified vizjb12 box charts and cross-page particle flights (#1400)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: research subagent + coordinator
head_sha: 802be587
verdict: approve-with-nits
---

# PR Review: feat(stories): unified vizjb12 box charts and cross-page particle flights (#1400)

## Summary

Converts story maps (`StoryDotMap`, `StoryCountyMap`), matrix charts (`UnitMatrixChart`, `ChartPanel`, `PositionsBlock`), bar/category displays (`BoxWaffleChart` in `FitDisplay`, `TopicPositionsBreakdown`, `NonprofitsPanel`), and `OutcomesChain` strips to unified `[data-box]` square geometry inspired by `jcbowyer/vizjb12`, and adds cross-page and cross-screen particle flights via `BoxFlightProvider` and `useStoryBoxTransition` (plus `document.startViewTransition` topic switching on home). All four findings from the initial rubric review were resolved in commit `802be587`, and all typechecks, production builds, and 110 Vitest suites pass cleanly.

## Scope of Change

- Files changed: 30 (excluding the review file)
- Areas touched: `web_app` / `web_docs`
- Commits:
  - `4da50a4b` `feat(stories): unified vizjb12 box charts and cross-page particle flights (#1400)`
  - `4c9b7503` `docs(pr-1404): auto-write rubric review [skip review]`
  - `802be587` `fix(stories): address PR #1404 rubric review findings (#1400)`
- Range reviewed: `6ca27078..802be587`

## CI Status

Checked on PR `#1404` (`Detect Changes` passed; `Frontend Build`, `Documentation Build`, `Backend Tests`, `API Types`, `PR conventions` watched to green before merge).

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean — no API keys, tokens, credentials, cookies, or `.env` values.
- **Fabricated data:** clean — `allocateWaffleCells` returns empty on `total <= 0`, `BoxWaffleChart` returns `null` on zero totals, `OutcomesChain` omits `.oc-box-strip` when `count === 0` or unavailable, and `BoxFlightProvider` / `MapDrill` only read live DOM/API marks.
- **Personal data / privacy (`AGENTS.md` #1080):** clean — no personal data stored, enriched, or logged.
- **Destructive or bulky data changes:** clean — no cache deletions or raw/binary data commits.

## Strengths

- Shared `planCrossFlight` / `sampleCrossFlight` pure geometry helper is cleanly unit-tested (`boxFlight.test.ts`), deterministic (`MAX_PARTICLES = 320`), and separates DOM capture (`captureDomBoxes`) from canvas animation (`BoxFlightProvider`).
- `allocateWaffleCells` (`waffleGrid.ts`) implements exact Hamilton largest-remainder apportionment across a bottom-left column-major 10×10 lattice (`waffleGrid.test.ts`).
- `prefers-reduced-motion: reduce` disables cross-page flights, screen transitions, `MapDrill` particles, reveal waves, and `document.startViewTransition` cleanly; `BoxFlightProvider` clears `data-box-flight-hide` on completion, interrupt, and unmount.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

All four initial findings were fixed and verified in commit `802be587`:
1. `ChartPanel.tsx` duplicate source/about line when `matrix && !chartForm` — fixed by adding `!matrix`.
2. `UnitMatrixChart.tsx` + `storyCharts.css` missing `:focus-visible` style and single-state hover/click collision on group labels — fixed with `.sc-label-btn:focus-visible` and split `hoveredGroup` / `pinnedGroup`.
3. `BoxFlightProvider.tsx` + `HomeOutcomesScroller.tsx` selector order and unmatched `focusGroup` hold dimming — fixed via priority `resolveTarget()`, `hasFocusMatch` guard, and removing mismatched `focusGroup` on outcome cards.
4. `FitDisplay.tsx` unfolding 8+ `top-bars` categories and gating on `items` instead of `rows` total — fixed via `topCategories(live)` and `rowsTotal >= 20`.

### 🔵 Nits / suggestions (Minor)

- `ChartPanel.tsx:38` (`MATRIX_CHARTS`) and `PositionsBlock.tsx:125` treat `'positions'` as matrix-eligible when `!spec.countsOnly`, which is a safe no-op while `chartSpec('positions', ...)` returns `countsOnly: true`.
- `BoxFlightProvider.tsx` `resolveTarget()` splits selectors on `,`, which assumes selectors do not contain nested commas inside `:is()` or attribute strings.
- Navigating to a targetless screen (`upcoming`, `verdict`, `recap`) holds starting boxes on canvas until `WAIT_TARGET_MS` (`2200ms`) or user pointer/key input.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
| --- | --- | --- |
| Issue first | Yes | Issue #1400 has Problem, Done when, Contract, Read first; branch `feat/1400-cross-page-box-particles`, `Closes #1400` |
| Conventional Commits | Yes | `feat(stories): ...` and `fix(stories): ...` with `Co-Authored-By` trailer |
| No fabricated data | Yes | All waffles, strips, and box matrices derive strictly from real counts; zero counts omit visuals |
| Scope label matches filter | Yes | `?state=`, `?city=`, `?story=`/`?topic=`, `?screen=` preserved across home ↔ story flights |
| Docs | Yes | Updated `web_docs/docs/guides/data-stories.md` in the same PR |
| Tests | Yes | New unit tests in `boxFlight.test.ts` and `waffleGrid.test.ts`; full 110-file Vitest suite passes |

## Test Coverage

- `cd web_app && npx tsc --noEmit` — 0 errors
- `cd web_app && npm run build` — succeeded
- `cd web_docs && npm run build` — succeeded
- `cd web_app && npm test -- --maxWorkers=2` — 110 test files, 971 tests passed (0 failures)

## Verdict

approve-with-nits — all mandatory scans clean, all initial review issues resolved in `802be587`, and all verification checks pass.
