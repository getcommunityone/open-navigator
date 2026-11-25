---
pr: 943
branch: fix/941-pk-post-hook-target
title: "fix(dbt): render gold_pk_post_hook at run time and let Postgres name the key"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 3d68c0efccd1f49921d248b316a75f796669f3e1
verdict: approve
---

# PR Review: fix(dbt): render gold_pk_post_hook at run time and let Postgres name the key

## Summary

Automated review (#648) for PR #943 on `fix/941-pk-post-hook-target`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/macros/gold_pk_post_hook.sql`
- `dbt_project/models/marts/dq_jurisdiction_mapping_summary.sql`
- `dbt_project/models/marts/dq_jurisdiction_mapping_summary_by_acs_income_level.sql`
- `dbt_project/models/marts/dq_jurisdiction_mapping_summary_by_acs_population_tier.sql`
- `dbt_project/models/marts/dq_jurisdiction_mapping_summary_municipality_places.sql`
- `dbt_project/models/marts/event_document_lexicon.sql`
- `dbt_project/models/marts/event_policy_bill.sql`
- `dbt_project/models/marts/event_policy_decision.sql`
- `dbt_project/models/marts/events_channels_search.sql`
- `dbt_project/models/marts/events_text_search.sql`
- `dbt_project/models/marts/jurisdiction_mapping_analysis.sql`
- `dbt_project/models/marts/jurisdiction_mapping_analysis_sources.sql`
- `dbt_project/models/marts/jurisdiction_state_aggregate.sql`
- `dbt_project/models/marts/serving_mdm_bridge_org_jurisdiction.sql`
- `dbt_project/models/marts/serving_mdm_organization.sql`
- `dbt_project/models/marts/serving_mdm_organization_nonprofit.sql`
- `web_docs/docs/development/non-blocking-table-rebuilds.md`

## CI Status

See the PR checks on `3d68c0efccd1`.

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
