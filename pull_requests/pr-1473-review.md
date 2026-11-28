---
pr: 1473
issue: 1411
verdict: approve-with-nits
---

# PR #1473 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `perf/1411-story-screen-mount`, `Refs #1411` (one part of a larger issue; the canvas maps in #1458 finish it).
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:**
  - `MemoPanel` deps list every value a panel's render closure reads; handlers go through refs so a stale closure can't call an old `answer` or `applyPlace`. The `active` flag moved to a store read by the frame, the vote frame, `StatRow` and the timeline panel; a story without the provider (topic stories) still gets `active` as a prop.
  - The flight context value is stable; `isFlying` is read on demand, and its two readers (`MapDrill`, the snapshot) read it at call time.
  - `captureDomBoxes` strides only above 1000 boxes, so small screens are unchanged.
- **Verification:** tsc, vitest (81 stance tests), production build; idle stillness check passes at 412x915 and 360x740; before and after frame timings in the PR body.
- **Nit:** the target of no long task over 100 ms is not met on the production build (median about 300 ms under load); the rest is native layout of the Overview's thousands of boxes.
- **Docs:** no contract change.

No blocking findings.
