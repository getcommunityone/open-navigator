---
pr: 971
branch: feat/970-overview-dot-map
title: "feat(web_app): story Overview shows a dot map of where data center meetings are"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 30dc6f567576a1a435dd939b330cc99a9bcdc819
verdict: approve
---

# PR Review: feat(web_app): story Overview shows a dot map of where data center meetings are

## Summary

Automated review (#648) for PR #971 on `feat/970-overview-dot-map`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `tests/test_api_data_center_meeting_mentions.py`
- `web_app/src/components/DotMatrixMap.tsx`
- `web_app/src/components/stance/StoryDotMap.test.ts`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/lib/dotMatrix.ts`
- `web_app/src/styles/stance.css`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `30dc6f567576`.

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
