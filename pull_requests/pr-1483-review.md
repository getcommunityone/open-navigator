---
pr: 1483
issue: 1458
verdict: approve-with-nits
---

# PR #1483 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `perf/1458-map-boxes`, `Refs #1458` (a part of it; the issue stays open for the 100 ms target).
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:** `MapBox`/`StateBox` take primitives and stable callbacks; the callbacks read the latest render's closures through a ref, so hover and pick behave as before. `useProgressiveCount` only grows, so drawn boxes are never remounted. The first slice is drawn at once, so a small map is unchanged.
- **Verification:** tsc, vitest (116 component tests), production build, hero-topic-switch before and after in the PR body.
- **Nit:** the 100 ms target is not met on this host (load 9 to 13); a flight started while the map is still filling lands on the boxes present when its count settles.
- **Docs:** no contract change.

No blocking findings.
