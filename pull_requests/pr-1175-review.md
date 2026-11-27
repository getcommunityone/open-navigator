---
pr: 1175
branch: fix/1174-home-hero
title: "fix(home): sticky Start the story, say a click opens the state, and name speakers on the map cards"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: f1e5b6b692323c330c78728dbc8323e3d3d81c9d
verdict: approve
---

# PR Review: fix(home): sticky Start the story, say a click opens the state, and name speakers on the map cards

## Summary

Automated review (#648) for PR #1175 on `fix/1174-home-hero`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `pull_requests/pr-1175-review.md`
- `tests/test_api_data_center_positions.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `f1e5b6b69232`.

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
