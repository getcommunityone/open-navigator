---
pr: 1003
branch: fix/1002-hide-empty-screens
title: "fix(web_app): story leaves out screens with nothing on record; map quotes show only on hover"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 0119daa1333dc2ef468f0c1fd77e013a1a40aba5
verdict: approve
---

# PR Review: fix(web_app): story leaves out screens with nothing on record; map quotes show only on hover

## Summary

Automated review (#648) for PR #1003 on `fix/1002-hide-empty-screens`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`

## CI Status

See the PR checks on `0119daa1333d`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**

## Agent review (Claude Code)

- **Filtering:** only `kind: 'chart'` screens drop, and only once `screenText(...).empty` is true. `empty` comes from `noData`, which is used only after the data has loaded, so loading screens stay.
- **Stability:** `.stance-acts` is keyed by the kept set. Without the key, GSAP's pin spacers made React's `removeChild` throw; this was reproduced and then fixed.
- **Landing:** when the list changes, the reader stays on the same screen id. A deep link to a dropped screen falls back to Overview.
- **No-default-quote:** neither map renders a card unless a state or pin is hovered or focused. Leaving the stage hides it.
- **Rubric scans:** clean. No data, API or docs contract changes.

Verdict stands: approve.
