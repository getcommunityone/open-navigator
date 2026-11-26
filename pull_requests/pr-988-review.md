---
pr: 988
branch: fix/987-story-map-hover
title: "fix(web_app): home story map no longer jitters on hover"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve
---

# PR Review: home story map no longer jitters on hover

Closes #987. The cause was a hover/height feedback loop, measured in a browser: the map moved on 25/25 hovers before the fix and 0/25 after. The change is two layout lines (a fixed readout height and top-aligned columns).

- Findings: none.
- Scans: none (layout only).
- Tests: `tsc` is clean; browser measurement above.

**approve**: merge when the required checks are green.
