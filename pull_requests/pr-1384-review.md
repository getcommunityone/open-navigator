---
pr: 1384
branch: fix/1380-phone-overview-map-size
title: "fix(web): phone Overview map fills the screen, compact header and stat row"
author: claude-code
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve-with-nits
---

## Scans

- Secrets / fabricated data / personal data / destructive: none. The stat row shows only real figures (`summaryStats`); the topic check's place counts are a Playwright route stub, test-only.

## Findings

- Nit: new phone rules use the existing 767px story breakpoint, not 640px, so tablets in portrait get the same layout as phones.
- Nit: a long topic name is ellipsized in the header select at phone width (the full name is still the selected option) to keep the headline to two lines.
- Nit: the state outline fallback (no county data) keeps its legend line; its other notes are hidden on the phone Overview.

## Notes

Scope label still matches the filter: "Showing Alabama · Why?" names the state shown and the reason is behind Why?. StoryCountyMap is untouched (CSS only). Desktop rules are unchanged (all inside the phone media query).

## Local checks

- `vitest run` -> 951 passed; `tsc --noEmit` clean
- `node e2e/phone-overview-map.check.mjs` -> all checks passed (360x740, 412x915; data center and topic story)
- `node e2e/story-header.check.mjs` -> no failures
