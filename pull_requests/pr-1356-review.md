---
pr: 1356
branch: feat/1348-dc-sites-over-time
title: "feat(stories): data centers over time screen and an honest recorded-meeting coverage line"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 62942cebe62d8b07e3f62cb919c8a6a788362d61
verdict: request-changes
---

# PR Review: feat(stories): data centers over time screen and an honest recorded-meeting coverage line

## Summary

Automated review (#648) for PR #1356 on `feat/1348-dc-sites-over-time`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/app.py`
- `api/main.py`
- `api/routes/data_center_sites_timeline.py`
- `api/routes/recorded_coverage.py`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_data_center_site_timeline.yml`
- `dbt_project/models/marts/data_center_site_timeline.sql`
- `dbt_project/models/staging/data_centers/stg_data_center_facility_registry.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `pull_requests/pr-1356-review.md`
- `tests/test_api_data_center_sites_timeline.py`
- `web_app/src/api/sitesTimeline.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/stance/CoverageLine.css`
- `web_app/src/components/stance/CoverageLine.tsx`
- `web_app/src/components/stance/SitesTimelinePanel.css`
- `web_app/src/components/stance/SitesTimelinePanel.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/utils/coverageLine.test.ts`
- `web_app/src/utils/coverageLine.ts`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/siteTimeline.test.ts`
- `web_app/src/utils/siteTimeline.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `62942cebe62d`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: **findings**
- Fabricated data / personal / destructive: see findings

## Strengths

- (blocked on scan findings below)

## Findings

### 🔴 Blocking (Critical)

- Possible secret or credential pattern matched: `(?i)postgres(ql)?://[^:\s]+:[^@\s]+@…`

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**request-changes**
