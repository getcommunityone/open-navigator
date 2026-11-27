---
pr: 1368
branch: fix/1367-map-drill-overview
title: "fix(stories): map drill to a state opens Overview, not a mid-story screen"
author: cursor-agent
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

## Scans

- Secrets: none
- Fabricated data in served path: none
- Personal data: none
- Destructive data changes: none

## Findings

None blocking.

## Notes

- Home drill hrefs and `applyPlace` now force `screen=overview`; `useStoryScreens` always re-lands on index 0 when `scopeKey` changes (fresh deep links with `?screen=` still work because `lastScope` is null on mount).
- `ScrollToTop` skipping `/stories/*` matches the #991/#1367 race (parent effect undoing the story land).
- Regression coverage: `map-taps.check.mjs` asserts Alabama carries `screen=overview` and lands on Overview.
- Docs updated in `data-stories.md`.

## Local checks

- Playwright: home → Alabama → `?state=AL&screen=overview`, pip 0, Overview headline in view.
- CI: pending at review time (Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions).

