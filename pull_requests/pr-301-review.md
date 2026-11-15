---
pr: 301
branch: feat/240-core-2-1-deep-link
title: "feat(web_app): open a meeting at the cited moment, and a citation link that names who and when"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: feat(web_app): open a meeting at the cited moment, and a citation link that names who and when

## Summary

Adds the ?t= deep link to the meeting page, a startAt prop on the player, a CitationLink component that never
invents a speaker or a time, and vitest for the helpers (27 tests). Builds clean. Closes #240. Approve with one nit.

## Scans

Secrets: clean. Fabricated data: none; missing speaker or time is shown as missing. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix.

Nit: the seek-on-load was not exercised in a browser here; it uses the same react-player call as the transcript cues.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #240 with its Contract posted before the first commit; epic and story table in the PR |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| Tests | Yes | vitest, run in CI |

## Verdict

Approve once the required checks are green.
