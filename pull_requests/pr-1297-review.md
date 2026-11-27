---
pr: 1297
branch: feat/1285-place-scope-zoom
title: "feat(stories): story scope steps up to a level with 5+ meetings, the home map zooms to the place, and the header has a one-click National"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator (agent self-review against .claude/review-rubric.md), after the github-actions auto-review
verdict: approve-with-nits
---

# PR Review: feat(stories): story scope steps up to a level with 5+ meetings, the home map zooms to the place, and the header has a one-click National

## Summary
The PR adds the owner's 5-meeting rule as one shared helper (`resolveStoryScope`, `MIN_SCOPE_MEETINGS = 5`) and applies it through `useStoryScope` on the home hero and on both story pages. Headline, counts, quotes and map use the resolved level, the URL keeps the reader's choice, and the reason is shown in plain words. The home map zooms to the state in effect, with the asked city pinned at its recorded coordinate. The header gets a one-click National on desktop and phones, the subtitle is reworded, and the topic-strip "AI reading" label is gone. Unit tests, typecheck, build, the docs build and both browser checks pass. CI was green on e8460e9a. Nothing is blocking; there are four nits. The left-column clipping from the issue could not be reproduced and goes to a follow-up.

## Scope of Change
- Files changed: 20 (+604 / -53, excluding review files)
- Areas touched: web_app, web_docs
- Commits:
  - 7bddfc1e feat(stories): story scope steps up …
  - e8460e9a Merge origin/main
  - da2bec33 docs(pr-1297): auto-write rubric review
- Range reviewed: `merge-base(origin/main)..e8460e9a`

## CI Status
| Check | Status |
|---|---|
| CI - Build & Test (e8460e9a) | success |
| PR conventions (e8460e9a) | success |
| Runs on da2bec33 (bot review commit) | action_required (bot-triggered; the code is identical) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. Every count shown is the caption-facts value, and the pin is the coordinate on the meeting record. With no coordinate on record the map says so and draws no pin. Test fixtures stay in tests.
- **Personal data:** clean. No personal fields.
- **Destructive data changes:** none.

## Strengths
- One pure, tested rule (11 unit tests: every fallback step, unknown counts, `scopeForLevel`). Callers only supply counts.
- The label, queries and map move together: each surface swaps in `placeScope.effective` at the one place its scope was derived.
- The URL stays the authority (CLAUDE.md scope rule). Home National is `?scope=national`, so refresh, deep links and the header agree.
- The story screen list and order are untouched, as coordinated.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `web_app/src/hooks/useStoryScope.ts`: while the caption facts load, the asked level is kept (by design), so a city page can render its city queries once and then switch to the state's. The second set of queries is cached afterwards. A small flash at most; verified in the browser.
- `web_app/src/hooks/useStoryScope.ts`: the pin lookup uses the data-center place counts for every topic. A city with no data-center meetings gets no pin, and the map then says so. A general place-coordinate endpoint would widen coverage.
- Home with a city that has 5 or more meetings but too few that took a side (for example Auburn): the map zooms to the state with the city pinned, while the title stays the wider place's under the reworded subtitle ("… Showing America."). Both are true, but the owner may want the map to follow the title there.
- The left-column clipping from #1285 did not reproduce. Tried: Chromium 390–1440px; Firefox and Chromium with classic scrollbars at 1000×1050 @2x and 1333×700 @1.5x; no element left of the viewport; no 100vw on the hero. It moves to a follow-up action item.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts | Yes | #1285, label ux-friction |
| Branch / PR naming, Closes | Yes | |
| Conventional Commits + attribution | Yes | |
| Docs with the change | Yes | guides/data-stories.md, development/story-captions.md |
| Scope label matches filter | Yes | The label shows the resolved level; the reason is visible; scope travels in the URL |
| No Fabricated Data | Yes | |
| Privacy | Yes | |

## Test Coverage
- **Unit:** `resolveStoryScope` (every step), `searchForNational` / `headerPlaceState` with `scope=national`, the updated subtitle wording.
- **Local runs:**
  - `npx tsc --noEmit`, `npx vitest run` (774 passed), `npm run build` and the docs build.
  - `node e2e/place-scope.check.mjs` at 1440 and Pixel 7.
  - `node e2e/map-taps.check.mjs` at Pixel 7, iPhone 13 and 1440.

## Verdict
approve-with-nits. Nothing has to change before merge.
