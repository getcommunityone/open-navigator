---
pr: 1336
branch: feat/1328-map-loading
title: "feat(stories): story and home maps load gracefully: reserved size, quiet skeleton, fade-in, no flash of another scope"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator (agent self-review against .claude/review-rubric.md)
verdict: approve-with-nits
---

# PR Review: story and home maps load gracefully

## Summary
The PR fixes the owner's "flashing stats in map before the map shows". While the shapes and counts load, the Overview now shows one skeleton box of the map's final size, with no stats and no other scope's map. The map, the comparison and the counts then fade in together. The four story and home maps share `MapSkeleton`, which has a calm slow/error state with Try again, and the national maps prefetch the county shapes on first hover. Throttled before/after runs confirm the flash is gone. Tests, typecheck, build and the docs build pass. Nothing is blocking; there are two nits.

## Scope of Change
- Files changed (this PR's own): 8 — MapSkeleton.tsx/.css (new), StoryScreenView, StoryStatesMap, StoryDotMap, StoryCountyMap, HomeDataStories, data-stories.md
- Areas touched: web_app, web_docs
- Commits:
  - c92be833 feat(stories): story and home maps load gracefully …
  - 7ea03bdc Merge origin/main (resolved StoryCountyMap: kept #1309's figure markup and added `map-fade-in`)
- Range reviewed: `75c14a45..7ea03bdc` (own changes)

## CI Status
| Check | Status |
|---|---|
| CI - Build & Test | see PR checks on the head commit |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. The skeleton shows no numbers, and nothing is invented while loading.
- **Personal data:** clean.
- **Destructive data changes:** none.

## Strengths
- One small component and hook, with no new query keys: the gate reuses the maps' own cached shape queries, so there are no extra requests.
- The Overview gate is scoped to the map slot only. The screen list and order are untouched, as coordinated.
- Reduced motion is respected for both the shimmer and the fade.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `MapSkeleton`'s default Try again refetches every active query on the page, a broad but safe choice. The map components pass their own `refetch` for shape errors.
- The story headline still shows the question ("What did local meetings in Georgia say…") for about a second before the caption facts arrive. That is the caption loader's placeholder, not another scope's data, and is out of scope here.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts | Yes | #1328, ux-friction |
| Branch / PR naming, Closes | Yes | |
| Conventional Commits + attribution | Yes | |
| Docs with the change | Yes | data-stories.md #1328 section |
| Scope label matches filter | Yes | No other scope's map or counts while loading |
| No Fabricated Data | Yes | |

## Test Coverage
- No unit tests for the skeleton's visual timing. It was verified with throttled Playwright filmstrips at 1440 and Pixel 7 (`/stories/data-centers?state=GA`, `/?state=GA`).
- Local runs: `npx vitest run` (852 passed), `tsc`, build, the docs build, `e2e/place-scope.check.mjs`, `e2e/map-taps.check.mjs`.

## Verdict
approve-with-nits. Nothing has to change before merge.
