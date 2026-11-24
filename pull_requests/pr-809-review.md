---
pr: 809
branch: feat/798-summary-provenance
title: "feat(web): a quiet how-this-summary-was-made panel on the decision page"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 2d040f5856ae968f289e61cb76947a3637e515ee
verdict: approve
---

# PR Review: feat(web): a quiet how-this-summary-was-made panel on the decision page

## Summary

Automated review (#648) for PR #809 on `feat/798-summary-provenance`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/provenance.py`
- `api/routes/decisions.py`
- `apps/lakebase-serving-sync/src/serving_tables.py`
- `dbt_project/contracts/event_analysis_provenance.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_event_analysis_provenance.yml`
- `dbt_project/models/marts/event_analysis_provenance.sql`
- `packages/hosting/scripts/neon/migrations/115_add_analysis_provenance_columns.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/llm/src/llm/enrichment/load_analysis_cache_to_bronze.py`
- `packages/llm/src/llm/gemini/meeting_transcript_policy.py`
- `tests/test_provenance_798.py`
- `web_app/src/components/AnalysisProvenance.test.ts`
- `web_app/src/components/AnalysisProvenance.tsx`
- `web_app/src/pages/DecisionDetail.tsx`
- `web_docs/docs/development/analysis-provenance.md`

## CI Status

See the PR checks on `2d040f5856ae`.

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
