---
pr: 992
branch: fix/991-story-lands-first
title: "fix(web_app): story lands on its screen with the headline in view"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve
---

# PR Review: story lands on its screen with the headline in view

Closes #991. The cause was confirmed by measurement: `--title` was 0.000 with the words offset 55px before the fix, and 1.000 with no offset after.
- The fix restores the story's one-hold-per-screen behaviour on the pinned layout.
- The three-stop rhythm stays available where a screen opts in with `[data-stop]` (the flow layout's existing rule). No current screen does, since the Challenge was retired in #982.

- Findings: none.
- Scans: none (UI behaviour only).
- Tests: `tsc` is clean; browser measurement above.

**approve**: merge when the required checks are green.
