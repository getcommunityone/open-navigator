---
pr: 1294
issue: 1291
verdict: approve-with-nits
---

# PR #1294 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1291-explorer-phone-compact`, `Closes #1291`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data (every figure still comes from the census bundle; the legend ticks are the real extent), no personal data, no data changes.
- **Correctness:**
  - Phone layout is gated on `max-width: 640px`; desktop markup is unchanged except the removed "Choropleth..." note.
  - The stage measures its box (ResizeObserver) and widens the viewBox height to the box aspect; the fit uses that height and label fonts are set in CSS px. With `compact` off, `vbH = H` and `pxUnit = 1`, so desktop is identical.
  - No information dropped: the breadcrumb keeps the full path in its title and a back link; the PLACE hint lives in the sheet (or a slim line when no sheet); the legend keeps its help panel; search and outline toggles are still reachable.
- **Verification:** Playwright at 360x740, 412x915 and 1440 (`web_app/e2e/explorer-compact.check.mjs`): map top inside the first viewport; tsc clean; vitest 760 pass.
- 🔵 Nit: the drill state (state, county, level) is still not in the URL, so the scope label and the scope do not survive a refresh. That predates this PR and is a follow-up.

No blocking findings.
