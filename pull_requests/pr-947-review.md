---
pr: 947
branch: perf/938-indexes-config-swap-guard
title: "perf(dbt): build every model's indexes before the swap and guard the large swaps"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: dbc75c4e2c8017bd5f4747ec3e6fe4e341afb25b
verdict: approve
---

# PR Review: perf(dbt): build every model's indexes before the swap and guard the large swaps

## Summary

Automated review (#648) for PR #947 on `perf/938-indexes-config-swap-guard`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/dbt_project.yml`
- `dbt_project/macros/ensure_search_indexes.sql`
- `dbt_project/macros/swap_guard.sql`
- `dbt_project/models/intermediate/int_browse_entity_transcripts.sql`
- `dbt_project/models/intermediate/int_decision_cause.sql`
- `dbt_project/models/intermediate/int_decision_topic.sql`
- `dbt_project/models/intermediate/int_jurisdictions.sql`
- `dbt_project/models/intermediate/int_transcript_keyword_cause.sql`
- `dbt_project/models/intermediate/int_transcript_keyword_topic.sql`
- `dbt_project/models/marts/_schema_data_center_meeting_mention.yml`
- `dbt_project/models/marts/_schema_data_center_meeting_position.yml`
- `dbt_project/models/marts/_schema_event_uncontested_item.yml`
- `dbt_project/models/marts/_schema_recent_transcribed_meeting.yml`
- `dbt_project/models/marts/bills.sql`
- `dbt_project/models/marts/contact_official.sql`
- `dbt_project/models/marts/event.sql`
- `dbt_project/models/marts/event_document_lexicon.sql`
- `dbt_project/models/marts/event_documents.sql`
- `dbt_project/models/marts/event_meeting_document.sql`
- `dbt_project/models/marts/grant.sql`
- `dbt_project/models/marts/grant_opportunity.sql`
- `dbt_project/models/marts/jurisdictions.sql`
- `dbt_project/models/marts/mdm_bridge_org_jurisdiction.sql`
- `dbt_project/models/marts/mdm_bridge_person_jurisdiction.sql`
- `dbt_project/models/marts/mdm_organization.sql`
- `dbt_project/models/marts/mdm_organization_government.sql`
- `dbt_project/models/marts/mdm_organization_nonprofit.sql`
- `dbt_project/models/marts/mdm_person.sql`
- `dbt_project/models/marts/person_government.sql`
- `dbt_project/models/marts/serving_grant.sql`
- `dbt_project/models/marts/serving_mdm_bridge_org_jurisdiction.sql`
- `dbt_project/models/marts/serving_mdm_organization.sql`
- `dbt_project/models/marts/serving_mdm_organization_nonprofit.sql`
- `dbt_project/models/marts/topic_transcript_link.sql`
- `web_docs/docs/development/non-blocking-table-rebuilds.md`

## CI Status

See the PR checks on `dbc75c4e2c80`.

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
