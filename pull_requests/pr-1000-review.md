---
pr: 1000
issue: 999
verdict: approve-with-nits
---

# PR #1000 review

Reviewed against `.claude/review-rubric.md`.

- **Issue/branch:** `fix/999-story-verdict-map-quote`, `Closes #999`, four-part issue.
- **Scans:** no secrets. Nothing is fabricated: the map card quotes the API's verbatim `evidence`, or shows nothing. No personal data, no data changes.
- **Match evidence rule:** the card renders `<mark>` through `highlightSnippet`, React-escaped.
- **Correctness:**
  - `primed` is set two frames after the master trigger is created, so later reports are honoured.
  - The settle guard ends on the first pointer/wheel/key/touch event or after 4s, so the reader is never held.
  - The scope change sits in the landing effect's dependencies, so the guard and re-land run again after a place change.
- **Nit:** while `settling` is on, a programmatic `goToRound` (e.g. the URL-change effect) won't update the active screen until the first input. Low risk: such moves follow a click.
- **Verification:** before/after browser reproductions are listed in the PR. tsc, eslint, build and tests pass.
