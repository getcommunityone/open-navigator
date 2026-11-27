---
pr: 1178
branch: fix/1176-home-hero-fits-screen
title: "fix(home): story hero fits one screen with Next story and a drill-down hint in view"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: coordinator (read-only pass over the diff, plus Playwright measurements)
verdict: approve
---

# PR Review: fix(home): story hero fits one screen with Next story and a drill-down hint in view

## Summary
Caps the home hero title at ~46px, puts Start the story + Next story directly under the subhead on every card (topic
cards gain Next story via the shared `nextStoryLink`), adds a scope line naming the active filter with a hint that a
state on the map opens its story, moves the data-center points under the buttons and caps the map at 60vh. Measured at
1366×768, 1440×900 and 390×844 for data centers and Flock (national and Tuscaloosa): buttons and scope line are in the
first screen, no horizontal scroll. Verdict: approve.

## Scope of Change
- Files: `HomeV9.tsx` (CSS), `HomeDataStories.tsx`, `HomeTopicStoryCard.tsx`, `web_docs/docs/guides/data-stories.md`
- Areas: web_app, web_docs

## Scans
- Secrets: clean. Fabricated data: clean (no new figures; Next story title comes from the live topic list; scope label
  is `storyScopeLabel`). Personal data: none. Destructive changes: none.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed on the branch.** The scope line said "Click a state", but phones tap (the story maps say "Tap" on phones,
  #1057). Changed to "Pick a state on the map to open its story." in the component and the guide.

### 🔵 Nits
- The map cap uses `svg[role="img"]` inside `.home-story-map`; if `StoryStatesMap` gains a second `role="img"` svg it
  would be capped too. Acceptable for now.
- At a city scope the map opens the *state* story (a broaden, not a drill into the city); the line says "a state",
  which is accurate.

## Local checks
- `npx tsc --noEmit`: clean
- `npx vitest run src/utils src/components`: 480 passed (51 files)
- `npm run build` (web_app): clean; docs build has only pre-existing broken-link warnings on other pages
