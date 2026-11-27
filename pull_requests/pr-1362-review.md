---
pr: 1362
branch: feat/1360-map-hover-drill-cue
title: "feat(stories): make clicking a hovered state to drill down obvious on maps"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

# PR Review: feat(stories): make clicking a hovered state to drill down obvious on maps

## Summary

Addresses #1360 so desktop users hovering a state on the home map (`StoryStatesMap`) or the Data Center Story Overview map (`StoryDotMap`) immediately see that clicking drills down into that state's story. Adds a pure, unit-tested SVG pill layout helper (`web_app/src/utils/mapHoverBadge.ts`) that renders a non-blocking teal `<State> · Click to drill down →` pill anchored to the hovered state (flipping below northern border states and clamping inside the SVG viewBox). Upgrades the left hover card's `.map-hover-open` link into a prominent teal pill button, clamps compact quotes to 2 lines so the button stays above the fold on laptops, and highlights the drill-down prompt under the map. Verified with Vitest, TypeScript/Vite build, Docusaurus build, and live Playwright hover & click checks across TX, WA, and ME. Verdict: **approve**.

## Scope of Change

- Files changed: 7 (+204 / -18, excluding review file)
- Areas touched: `web_app`, `web_docs`
- Commits:
  - `233d1cbb` `feat(stories): make clicking a hovered state to drill down obvious on maps (#1360)`
- Range reviewed: `origin/main..HEAD`

## CI Status

| Check | Status |
|---|---|
| Frontend Build | Pending on push (passed locally: `vitest` 26/26, `tsc && vite build`) |
| Documentation Build | Pending on push (passed locally: `cd web_docs && npm run build`) |
| Backend Tests | Pending on push (no backend files changed) |
| API Types | Pending on push (no API files changed) |
| PR conventions | Pending on push |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean (pre-commit secret/private-key checks passed; diff inspected).
- **Fabricated data in a served path:** clean (UI affordances only; state names and counts come from real API/TopoJSON data).
- **Personal data & privacy (`AGENTS.md` #1080):** clean (no personal data added, stored, or logged).
- **Destructive or bulky data changes:** clean (no deletions or raw data committed).

## Strengths

- `pointerEvents="none"` on `[data-hover-drill-cue]` ensures the on-map pill never intercepts clicks or causes hover flicker.
- Pure viewBox clamping and top-edge flipping (`layoutHoverBadge`) cleanly handles border states (WA, ME, AK) without hard-coded state coordinates.
- Compact quote 2-line clamp keeps the teal `Click <State> to open its story →` button comfortably above the fold (`bottom: 705–726px` at 1440×900).
- Governed guide (`web_docs/docs/guides/data-stories.md`) and e2e check (`web_app/e2e/map-taps.check.mjs`) updated in the same PR.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Issue #1360 has Problem, Done when, Contract, Read first; branch `feat/1360-map-hover-drill-cue`; PR has `Closes #1360` |
| Conventional Commits | Yes | `feat(stories): ...`, `docs(review): ...` with co-author trailer |
| No fabricated data | Yes | Only real state names and existing served data |
| Scope label matches filter | Yes | Clicking any state navigates with `?state=<code>` unchanged |
| Match evidence on filtered tiles | Yes | Existing `highlightSnippet` quote rendering untouched |
| Docs | Yes | Updated `web_docs/docs/guides/data-stories.md` |
| Tests | Yes | Added 4 unit tests (`mapHoverBadge.test.ts`), updated `e2e/map-taps.check.mjs`, ran live Playwright check |

## Test Coverage

- `cd web_app && npx vitest run src/utils/mapHoverBadge.test.ts src/utils/mapQuote.test.ts src/components/stance/QuoteCard.test.tsx`: 26 passed (26)
- `cd web_app && npm run build`: passed (`tsc && vite build`)
- `cd web_docs && npm run build`: succeeded
- Live Playwright check at 1440×900 on `http://localhost:5173/`: confirmed TX, WA, ME show `<State> · Click to drill down →` inside the SVG viewBox, `.map-hover-open` stays above the fold (`705–726px`), and clicking TX navigates to `/stories/data-centers?state=TX`.

## Verdict

**approve** — clean, scoped UX fix with unit, build, docs, and live browser verification; ready to merge once required CI checks are green.
