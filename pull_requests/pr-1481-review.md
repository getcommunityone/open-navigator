---
pr: 1481
branch: feat/1418-heat-concern-by-topic
title: "feat(api): per-year speaker heat and top concern per topic and place"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: f11e919cacea5fde4e2a653bafedd78290eb85b3
verdict: approve
---

# PR Review: feat(api): per-year speaker heat and top concern per topic and place

## Summary

Automated review (#648) for PR #1481 on `feat/1418-heat-concern-by-topic`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/topic_heat_year.odcs.yaml`
- `dbt_project/contracts/topic_top_concern.odcs.yaml`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_topic_heat_year.yml`
- `dbt_project/models/marts/topic_heat_year.sql`
- `dbt_project/models/marts/topic_top_concern.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `pull_requests/pr-1481-review.md`
- `tests/test_api_topic_heat_concern.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/chart/insightFacts.test.ts`
- `web_app/src/components/chart/insightFacts.ts`
- `web_app/src/components/chart/useInsightHeatConcern.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/stance/HeatYearBoxes.test.tsx`
- `web_app/src/components/stance/HeatYearBoxes.tsx`
- `web_app/src/components/stance/TimelineChart.tsx`
- `web_app/src/components/stance/TopicCountyMap.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/chartInsight.test.ts`
- `web_app/src/utils/chartInsight.ts`
- `web_docs/docs/development/chart-title-and-legend-rule.md`

## CI Status

See the PR checks on `f11e919cacea`.

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
