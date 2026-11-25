---
pr: 968
branch: docs/956-dc-sources-citations
title: "feat(data-centers): cite the hearing trackers and inventories, block the ones we may not use, feed leads from the CC BY trackers"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: b13c45174e4984f936669db379eb5b4bfd85cc72
verdict: approve
---

# PR Review: feat(data-centers): cite the hearing trackers and inventories, block the ones we may not use, feed leads from the CC BY trackers

## Summary

Automated review (#648) for PR #968 on `docs/956-dc-sources-citations`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/models/intermediate/_schema_int_data_center_hearing_lead.yml`
- `dbt_project/models/intermediate/int_data_center_hearing_lead.sql`
- `dbt_project/models/marts/_schema_data_center_hearing.yml`
- `dbt_project/models/marts/data_center_hearing.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/data_centers/_schema_stg_data_center_hearing_tracker_lead.yml`
- `dbt_project/models/staging/data_centers/stg_data_center_hearing_tracker_lead.sql`
- `packages/ingestion/src/ingestion/data_centers/community_events.py`
- `packages/ingestion/src/ingestion/data_centers/fetch_hearing_sources.py`
- `packages/ingestion/src/ingestion/data_centers/load_hearing_tracker_leads.py`
- `packages/ingestion/tests/test_community_events.py`
- `packages/ingestion/tests/test_load_hearing_tracker_leads.py`
- `web_docs/docs/data-sources/citations.md`
- `web_docs/docs/development/data-center-hearings.md`
- `web_docs/docs/development/data-center-source-review.md`

## CI Status

See the PR checks on `b13c45174e49`.

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
