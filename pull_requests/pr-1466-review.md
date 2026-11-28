---
pr: 1466
issue: 1463
verdict: approve
---

# PR #1466 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1463-story-national`, `Closes #1463`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:** the header toggle and a place pick remount the page (Layout pick marker); the fresh story instance cannot detect a place change, so the carried `?screen=` must already be Overview. Only `/stories/:id` paths are touched, and only when `screen` is present.
- **Verification:** `story-scroll` National case passes 3 of 3 on a production build (failed on main); vitest `headerPlace` 24 passed. The check now waits for Overview and holds 2 s, so a land-then-revert still fails.
- **Docs:** no contract change.

No blocking findings.
