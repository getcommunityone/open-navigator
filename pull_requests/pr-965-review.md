---
pr: 965
branch: fix/964-story-next-button
title: "fix(web_app): story Next buttons sit at the right like Start the story and read Next →"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: 49a4e916
verdict: approve
---

# PR Review: story Next buttons sit at the right like Start the story

## Summary

The Data Story step buttons read "Next: Who spoke up" and sat inline after Back, which the owner found confusing. They
now match "Start the story": one primary **Next →** button at the bottom right, with **← Back** at the left. The
destination is kept as the accessible name and tooltip ("Next: Who spoke up"), so screen readers still hear it.

## Scope of Change

- `web_app/src/components/stance/ScreenNav.tsx`, `StoryVoteScreens.tsx`: the split layout and the label.
- `web_app/src/styles/stance.css`: `.stance-nav-split` (space-between) and `.stance-next-end` (pushed right, min width).
- `web_docs/docs/guides/data-stories.md`: describes the new buttons.

## Scans

- Secrets, fabricated data, personal data, destructive changes: none (layout and copy only).

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- The visible label no longer names the next screen. That is the owner's request; the name stays in `aria-label` and
  `title`.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/964-…`, `Closes #964` |
| Conventional Commits | ✅ | |
| Docs with the change | ✅ | `guides/data-stories.md` |
| Tests | ✅ | vitest 379 passed; `tsc` clean |

## Test Coverage

- Checked in Chromium at 1280px and 375px: Back at the left, Next at the right, no overlap. The accessible name is
  "Next: Who spoke up".

## Verdict

**approve**: merge when the required checks are green.
