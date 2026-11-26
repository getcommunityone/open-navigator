---
pr: 1058
branch: fix/1057-story-map-tap
title: "fix(stories): story maps say Tap on phones, and a tap selects a county"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 1987b642480c527592d0d06d17425058a77aa2e7
verdict: approve
---

# PR Review: fix(stories): story maps say Tap on phones, and a tap selects a county

## Summary

Automated review (#648) for PR #1058 on `fix/1057-story-map-tap`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/utils/touchOnly.test.ts`
- `web_app/src/utils/touchOnly.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `1987b642480c`.

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

## Agent review

- Issue and branch: fix/1057-story-map-tap, Closes #1057; four parts present.
- Scans: no secrets, no data, no personal data, no fabricated numbers (wording only).
- Correctness: isTouchOnly guards a missing window/matchMedia and returns false, so desktop and SSR keep the Hover wording; county and ring taps only set the selected county (no navigation), so the readout and quote card work on touch; state taps keep narrowing the story.
- Checks: vitest 13 passed, tsc clean. Docs: guides/data-stories.md.

No blocking findings.
