---
pr: 1168
branch: feat/1140-timeline-dumbbell
title: "feat(stories): Meetings screen becomes a trend line with a milestone track, plus a period dumbbell and unit matrix, for every topic"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 51fa7bda6be250c292e23c992f2117969a375dfe
verdict: approve
---

# PR Review: feat(stories): Meetings screen becomes a trend line with a milestone track, plus a period dumbbell and unit matrix, for every topic

## Summary

Automated review (#648) for PR #1168 on `feat/1140-timeline-dumbbell`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/data_centers.py`
- `api/routes/topic_timeline.py`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_recorded_meeting_year.yml`
- `dbt_project/models/marts/recorded_meeting_year.sql`
- `tests/test_api_topic_timeline.py`
- `web_app/src/api/topicTimeline.ts`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/DumbbellChart.tsx`
- `web_app/src/components/stance/TimelineChart.tsx`
- `web_app/src/components/stance/UnitMatrixChart.tsx`
- `web_app/src/components/stance/storyCharts.css`
- `web_app/src/components/stance/useChartWidth.ts`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_app/src/utils/storyTimeline.test.ts`
- `web_app/src/utils/storyTimeline.ts`
- `web_app/src/utils/unitMatrix.test.ts`
- `web_app/src/utils/unitMatrix.ts`
- `web_docs/docs/development/story-charts-timeline-dumbbell.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `51fa7bda6be2`.

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
