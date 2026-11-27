---
pr: 1318
branch: feat/1307-home-state-county-map
title: "feat(home): a state-scoped home hero draws the story's county map, not a cropped box grid"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: b50e8380300b934fb7de4bfb7f1c906c198aae94
verdict: approve
---

# PR Review: feat(home): a state-scoped home hero draws the story's county map, not a cropped box grid

## Summary

Automated review (#648) for PR #1318 on `feat/1307-home-state-county-map`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/place-scope.check.mjs`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `b50e8380300b`.

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
