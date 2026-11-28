---
pr: 1385
branch: perf/1382-slim-topic-organization
title: "perf(topics): slim the published nonprofits-by-topic table to fit Neon"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude (read-only reviewer subagent + author verification)
head_sha: e3740525e58cf0da6bfb220b99b43c761f39e088
verdict: approve-with-nits
---

# PR Review: perf(topics): slim the published nonprofits-by-topic table to fit Neon

## Summary

Automated review (#648) for PR #1385 on `perf/1382-slim-topic-organization`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_organizations.py`
- `api/routes/topic_upcoming.py`
- `dbt_project/contracts/organization_event.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/topic_organization_count.odcs.yaml`
- `dbt_project/contracts/topic_organization_serving.odcs.yaml`
- `dbt_project/contracts/topic_upcoming.odcs.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_organization_event.yml`
- `dbt_project/models/marts/_schema_topic_organization.yml`
- `dbt_project/models/marts/_schema_topic_organization_serving.yml`
- `dbt_project/models/marts/_schema_topic_upcoming.yml`
- `dbt_project/models/marts/organization_event.sql`
- `dbt_project/models/marts/topic_organization.sql`
- `dbt_project/models/marts/topic_organization_count.sql`
- `dbt_project/models/marts/topic_organization_serving.sql`
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
- `pull_requests/pr-1377-review.md`
- `tests/test_api_topic_organizations.py`
- `tests/test_api_topic_upcoming.py`
- `web_app/src/api/topicOrganizations.ts`
- `web_app/src/api/topicUpcoming.ts`
- `web_app/src/components/stance/UpcomingPanel.tsx`
- `web_app/src/utils/topicOrganizations.test.ts`
- `web_app/src/utils/topicOrganizations.ts`
- `web_app/src/utils/topicUpcoming.test.ts`
- `web_app/src/utils/topicUpcoming.ts`
- `web_docs/docs/development/organization-events.md`
- `web_docs/docs/development/topic-organizations.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `e3740525e58c`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important) — found by the reviewer, fixed on the branch

- The 280-character cut started at the beginning, so a passage whose first `<mark>` sat later lost its highlight (match-evidence rule). Now the window starts 100 characters before the first mark, cuts at words, and drops the last word only when it stops before the end. Checked on the build: 0 evidence rows without a mark, 0 with unbalanced marks (13,813 rows).
- A city whose nonprofits are all outside its state's served rows showed a confident 0. Now `partial` compares the state's total with the rows actually served for it (including every named-in-meeting row), stays true when the city shows none, and the screen says "None of <city>'s nonprofits on record are among its state's strongest" instead of "none on record". Test added.

### 🔵 Nit (Minor) — fixed

- Mark balance now counts `<mark>` against `</mark>`, not every `<`.
- The count model's comment said 40; it is 20.

Checked by the reviewer: yml and SQL columns match; the API reads only served columns; no person data or invented numbers.

## Verdict

**approve-with-nits**: the findings were fixed on the branch and re-tested.
