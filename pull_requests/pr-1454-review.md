---
pr: 1454
issue: 1440
verdict: approve
---

# PR #1454 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1440-story-still`, `Closes #1440`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:**
  - The fit loop was a limit cycle between the figure's zoom and its chart's layout width. The zoom now only goes down inside a 1.5 s burst, is kept when a late measure lands within 0.04, and the observers stop after 6 measures in 2 s. A real resize re-arms them.
  - The flight now ends when its target exists but has no boxes after 0.5 s; targets not yet in the DOM still wait the full 2.2 s.
- **Verification:** width sweep 320 to 430 of Sites: all still after the change (two sizes cycled before); the new idle check passes on every screen at 412x915 and 360x740; tsc and build pass.
- **Not covered:** box-coverage clipped headlines on Agendas and Gatherings are a landing problem, tracked separately.
- **Docs:** no contract change.

No blocking findings.
