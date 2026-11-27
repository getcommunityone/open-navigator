---
pr: 1219
branch: fix/1207-timeline-thin-coverage
title: "fix(stories): thinly recorded years draw hollow and dashed, the chart opens on the share, and milestones return in production"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: a1c0a35d93c4385d4c7fdba21930bf81cadcfa09
verdict: approve
---

# PR Review: fix(stories): thinly recorded years draw hollow and dashed, the chart opens on the share, and milestones return in production

## Summary

Automated review (#648) for PR #1219 on `fix/1207-timeline-thin-coverage`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/topic_timeline.py`
- `tests/test_api_topic_timeline.py`
- `web_app/src/components/stance/TimelineChart.tsx`
- `web_app/src/components/stance/storyCharts.css`
- `web_app/src/utils/storyTimeline.test.ts`
- `web_app/src/utils/storyTimeline.ts`
- `web_docs/docs/development/story-charts-timeline-dumbbell.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `a1c0a35d93c4`.

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
