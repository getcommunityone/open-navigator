---
pr: 1342
issue: 1341
verdict: approve
---

# PR #1342 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1341-clear-home-link`, `Closes #1341`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Scope rule:** the home mark and menu Home keep `?state=&city=` (or `scope=national`), so the label and data stay in the chosen place.
- **Layout:** header checked at 360, 412 and 1440 (no overflow, one row, toggle on screen). The story top bar layout (#1339) is untouched; only the × gained a caption and tooltip.
- **Checks:** `e2e/home-link.check.mjs` passes, vitest 886 pass, tsc clean.
