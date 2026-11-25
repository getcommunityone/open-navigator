---
pr: 986
branch: fix/985-home-story-map
title: "fix(web_app): home Data stories box names the story and maps linked states"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: home Data stories box names the story and maps linked states

## Summary
Closes #985.
- **The box:** it names the story and its question, shows the place's real counts with a scoped Start button, and
  lists every story.
- **The map:** one linked marker per state with real meeting counts.
- **Fixes along the way:**
  - the stories registry moves to `utils` so the home page doesn't pull the story's chunk;
  - the site credit no longer narrows itself from a capped sample.

## Findings
- 🔴 None.
- 🟡 None.
- 🔵 Nits:
  - The map adds one national meeting-mentions call (`limit=1`) per home visit, cached for 5 minutes.
  - Markers sit at Albers centroids; Alaska and Hawaii are shown in their inset positions.

## Scans
- Secrets, personal data, destructive changes: none.
- Fabricated data: none. Every marker and count is from the API, a state with none has no marker, and there is one
  story, said so plainly.

## Tests
- `tsc` is clean; vitest 404; eslint is clean.
- Browser:
  - 50 markers; a marker click opens the state's story.
  - The highlighted place shows its counts.
  - 375px has no horizontal scroll; no API or page errors.

## Verdict
**approve-with-nits**: merge when the required checks are green.
