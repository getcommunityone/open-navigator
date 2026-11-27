---
pr: 1296
branch: feat/1288-story-kpi-drilldown
title: "feat(stories): tap a \"Who spoke up\" number to see the records behind it"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 70f33c0bb3a415408cf921f036e65441787f4c6a
verdict: approve
---

# PR Review: feat(stories): tap a "Who spoke up" number to see the records behind it

## Summary

Automated review (#648) for PR #1296 on `feat/1288-story-kpi-drilldown`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/app.py`
- `api/main.py`
- `api/routes/data_center_drill.py`
- `tests/test_api_data_center_drill.py`
- `web_app/src/api/storyDrill.ts`
- `web_app/src/components/stance/CommentMetricsBlock.tsx`
- `web_app/src/components/stance/KpiDrill.css`
- `web_app/src/components/stance/KpiDrill.test.tsx`
- `web_app/src/components/stance/KpiDrill.tsx`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/lib/api.types.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `70f33c0bb3a4`.

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
