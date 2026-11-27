---
pr: 1339
issue: 1337
verdict: approve-with-nits
---

# PR #1339 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1337-phone-story-header`, `Closes #1337`; the issue has all four parts.
- **Scans:** no secrets, no personal data, no data changes. No fabricated figures: every summary fact comes from the story's own counts or positions data and is left out when that data is missing (unit tested).
- **Correctness:**
  - The scope note moved into the headline's column and the bar wraps on phones, so the two cannot overlap; the e2e check asserts it at 360x740 and 412x915, with the note closed and open.
  - The note's text still comes from `resolveStoryScope`; the new `short` line is derived from the same counts, so the label matches the data shown.
  - Caption, stance-evidence and map-loading code are untouched; the rebase onto #1336 only needed the `map-fade-in` wrapper kept.
- **Nits:**
  - Screens taller than a viewport still scroll inside their own frame; only the Overview was re-paged. Worth its own issue.
  - `story-scroll.check.mjs` last desktop check fails the same way on unmodified main; not this PR.
- **Checks run:** vitest 859 pass, tsc clean, `story-header.check.mjs` passes at both sizes.
