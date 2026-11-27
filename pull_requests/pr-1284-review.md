---
pr: 1284
issue: 1282
verdict: approve
---

# PR #1284 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1282-overview-first`, `Closes #1282`; the issue has all four parts.
- **Scans:** no secrets, no personal data, no data changes. No fabricated data: the points, subhead, basis, lede and notes are the same values the cover showed, now rendered in Overview's left column.
- **Correctness:** `startRef`/`onCover` are removed and nothing indexes a removed screen; Next from screen 1 goes to screen 2, Back and the phone bar's Back are hidden on screen 1, swipe and keys use the same `goTo`. `storyStartHref` still sets `?screen=overview`. Place-scope resolution and labels are untouched.
- **Verification:** tsc clean, vitest 747 passed, Firefox at 1440 and 412 wide on the Data Center Story (national, AL) and short-term rentals (CA).
- **Docs:** `web_docs/docs/guides/data-stories.md` updated.
- **Nit:** on a phone the points sit after the map, not before it, to keep the map near the headline.

No blocking findings.
