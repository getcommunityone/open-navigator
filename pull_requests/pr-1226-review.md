---
pr: 1226
branch: fix/1221-search-org-types
title: "fix(search): search pickers offer Organizations with real sub-types, Places and Grant Opportunities"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 2878e1489c8a33cf6cd3bddd01eed71e32a4dcdc
verdict: approve
---

# PR Review: fix(search): search pickers offer Organizations with real sub-types, Places and Grant Opportunities

## Summary

Automated review (#648) for PR #1226 on `fix/1221-search-org-types`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/search.py`
- `api/routes/search_postgres.py`
- `dbt_project/models/marts/mdm_organization.sql`
- `tests/test_api_search_org_types.py`
- `web_app/src/lib/searchCategories.test.ts`
- `web_app/src/lib/searchCategories.ts`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/UnifiedSearch.tsx`
- `web_docs/docs/guides/unified-search.md`

## CI Status

See the PR checks on `2878e1489c8a`.

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
