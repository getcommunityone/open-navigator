---
pr: 1377
branch: feat/1347-org-events
title: "feat(topics): upcoming events of topic nonprofits from their own websites, folded into Coming up"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 56aa0c7a7ba1a623b2ed1cef9ed20ecfc4397fbf
verdict: approve
---

# PR Review: feat(topics): upcoming events of topic nonprofits from their own websites, folded into Coming up

## Summary

Automated review (#648) for PR #1377 on `feat/1347-org-events`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_upcoming.py`
- `dbt_project/contracts/organization_event.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/topic_organization.odcs.yaml`
- `dbt_project/contracts/topic_upcoming.odcs.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_organization_event.yml`
- `dbt_project/models/marts/_schema_topic_organization.yml`
- `dbt_project/models/marts/_schema_topic_upcoming.yml`
- `dbt_project/models/marts/organization_event.sql`
- `dbt_project/models/marts/topic_organization.sql`
- `dbt_project/models/marts/topic_upcoming.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_org_events__event.sql`
- `dbt_project/models/staging/stg_org_events__website.sql`
- `packages/ingestion/src/ingestion/org_events/__init__.py`
- `packages/ingestion/src/ingestion/org_events/crawl.py`
- `packages/ingestion/src/ingestion/org_events/db.py`
- `packages/ingestion/src/ingestion/org_events/fetch.py`
- `packages/ingestion/src/ingestion/org_events/parse.py`
- `packages/ingestion/src/ingestion/org_events/websites.py`
- `packages/ingestion/tests/test_org_events.py`
- `tests/test_api_topic_upcoming.py`
- `web_app/src/api/topicUpcoming.ts`
- `web_app/src/components/stance/UpcomingPanel.tsx`
- `web_app/src/utils/topicUpcoming.test.ts`
- `web_app/src/utils/topicUpcoming.ts`
- `web_docs/docs/development/organization-events.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `56aa0c7a7ba1`.

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
