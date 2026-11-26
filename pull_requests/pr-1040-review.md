---
pr: 1040
issue: 1039
verdict: approve
---

# PR #1040 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1039-state-county-story-map`, `Closes #1039`; the issue has all four parts.
- **Scans:** no secrets, no personal data, no data changes. No fabricated data: every shade is a real `count(DISTINCT video_id)`
  from `data_center_meeting_mention`; a county with none uses the empty colour; a government that can't be placed is named,
  not guessed into a county.
- **Correctness:**
  - `by_place` is filtered with the same `_mention_where` as the other counts (state, site, strength) and never by city, so the
    state map isn't emptied by a city scope; the city's county is highlighted instead. Georgia's governments sum to the scope's
    meeting total (118 = 118), so no meeting is counted twice.
  - The place query runs in its own `try`, so a serving copy without `jurisdictions` returns an empty `by_place` and the map
    falls back to the national view rather than failing the endpoint.
  - `albersPoint` uses `geoAlbersUsa().scale(1300).translate([487.5, 305])`, the projection us-atlas's albers files are
    built with, so coordinates land on the same county shapes (verified visually: Columbus sits in Muscogee).
  - Scope label: the caption names the state ("by county · Georgia") and the city when one is in scope, matching the filter.
- **Checks:** tsc clean, vitest stance suite passes; CI runs on the PR.
- **Docs:** `guides/data-stories.md` updated.

No blocking findings.
