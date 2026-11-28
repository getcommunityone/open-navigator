---
pr: 1489
issue: 1485
verdict: approve
---

# PR #1489 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1485-flight-landing-smooth`, `Closes #1485`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data (single-box screens are the existing empty state, group `none`), no personal data.
- **Correctness:**
  - Planning waits for a stable layout fingerprint and gives up after 1.7 s, so a screen that never settles still flies, and the live retarget keeps the landing exact.
  - `retargetPlan` only reads rects; the one write (`data-box-flight-reveal`) happens after the last read of a frame.
  - Reduced motion draws no canvas; the new boxes fade in over 160 ms. Interrupt and unmount both clear the hide and reveal marks.
  - HTML boxes no longer take `fill` (black); colour comes from the background.
- **Verification:** `box-flight-landing.check.mjs` 0.00 px over 51 flights at 412x915 and 1440x900 (before: up to 267 px); unit tests 823 pass; `story-still` OK; perf check shows the same long-task profile as main.
- **Docs:** `web_docs/docs/guides/data-stories.md` section added.

No blocking findings.
