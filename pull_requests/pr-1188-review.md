---
pr: 1188
branch: fix/1187-map-card-open-button
title: "fix(stories): map card opens the state story with a full-width button; compact legend under the map"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: coordinator (read-only pass over the diff, plus Playwright measurements)
verdict: approve
---

# PR Review: fix(stories): map card opens the state story with a full-width button; compact legend under the map

## Summary
Replaces the map hover card's caption-sized "Click to open the story for X →" with a full-width 44px link button, and
compacts the caption, legend and method note under `StoryStatesMap` so the home page's first desktop screen keeps room
for Browse topics. Verdict: approve.

## Scans
- Secrets, fabricated data, personal data, destructive changes: clean. No new figures; the AI-reading label stays in the
  legend; the method note moved into the disclosure, not removed.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None. Checked: the card stays open while the pointer moves onto it (hover clears on the stage's `onMouseLeave`, and the
card is inside the stage), so the button is clickable on desktop; on phones the same link replaces the old text link.

### 🔵 Nits
- The method note is now one click away. The legend still says "AI reading of meetings", so the AI label stays visible.
- `StoryDotMap` / `StoryCountyMap` keep "Show data table"; harmonising those labels is optional.

## Local checks
- `npx tsc --noEmit`: clean; `npx vitest run src`: 63 files, 588 tests passed
- Playwright: button 256×44px at 15px; map block bottom 651 → 588 px at 1366×768
