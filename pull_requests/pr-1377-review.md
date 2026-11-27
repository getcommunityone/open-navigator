---
pr: 1377
branch: feat/1347-org-events
title: "feat(topics): upcoming events of topic nonprofits from their own websites, folded into Coming up"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude (read-only reviewer subagent + author verification)
head_sha: 56aa0c7a7ba1a623b2ed1cef9ed20ecfc4397fbf
verdict: approve-with-nits
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

### 🔴 Blocking (Critical) — found by the reviewer, fixed on the branch

- Time zones: an iCal UTC time (`...Z`) was dated in UTC (a 7 PM EST event on Dec 5 became Dec 6) and the mart re-rendered times in the server's zone. Fixed: a UTC time is moved to the calendar's own zone (X-WR-TIMEZONE or its one VTIMEZONE) and is not used without one; JSON-LD keeps its written offset; the local wall clock is stored as text (`start_time` → `organization_event.event_time`), never re-rendered. A JSON-LD `Z` time is not used.
- Redirects: the client followed redirects before checking each hop's robots.txt. Fixed: `follow_redirects=False`, each hop is checked against its host's robots.txt, paced and blocked per host before it is requested (test: a redirect to a disallowed host is never fetched).

### 🟡 Should fix (Important) — fixed

- `VALUE=DATE` matched `VALUE=DATE-TIME`; params are now parsed and compared exactly.
- An event was labelled with the host's home city; `jurisdiction_name` is now null for nonprofit events (listed under the host's state).
- `max_bytes` did not cap the download; responses are streamed and cut at the cap.
- A re-crawl never removed cancelled events; a successful read now deletes that site's future events it no longer lists.

### 🔵 Nit (Minor) — fixed

- Dead `^webcal:` alternative removed; iCal text is unescaped in one pass.

Checked by the reviewer: the four `topic_upcoming` union branches line up column by column (28 columns); no person data is stored; the User-Agent, pacing and 403/429 stop hold.

## Verdict

**approve-with-nits**: the blocking and should-fix findings were fixed on the branch and re-tested (16 ingestion tests, dbt rebuild).
