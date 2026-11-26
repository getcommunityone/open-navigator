---
pr: 1094
branch: feat/1087-home-box-map
title: "feat(home): the data center map as state-shaped boxes split by speakers for, against and neutral"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 14115ddffc3ee34aef463ee3cf5c568f6c54113e
verdict: approve
---

# PR Review: feat(home): the data center map as state-shaped boxes split by speakers for, against and neutral

## Summary

Automated review (#648) for PR #1094 on `feat/1087-home-box-map`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `tests/test_api_data_center_positions.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/boxSplit.test.ts`
- `web_app/src/utils/boxSplit.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `14115ddffc3e`.

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
