---
pr: 1464
branch: feat/1399-trending-terms
title: "feat(trends): trending terms and hot words from meeting speech"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 210e93300ec17501e7806ee3d3f959b28cde9b4e
verdict: approve
---

# PR Review: feat(trends): trending terms and hot words from meeting speech

## Summary

Automated review (#648) for PR #1464 on `feat/1399-trending-terms`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/trending_terms.py`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/trending_term.odcs.yaml`
- `dbt_project/contracts/trending_term_evidence.odcs.yaml`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/trending_terms/_schema_trending_terms.yml`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__candidate.sql`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__hot.sql`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__jurisdiction_year.sql`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__meeting.sql`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__name_lexicon.sql`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__official_name.sql`
- `dbt_project/models/intermediate/trending_terms/int_trending_term__sample_term.sql`
- `dbt_project/models/marts/_schema_trending_term.yml`
- `dbt_project/models/marts/trending_term.sql`
- `dbt_project/models/marts/trending_term_evidence.sql`
- `dbt_project/seeds/schema.yml`
- `dbt_project/seeds/trending_term_common_word.csv`
- `dbt_project/seeds/trending_term_excluded.csv`
- `dbt_project/seeds/trending_term_public_figure.csv`
- `dbt_project/seeds/trending_term_sensitive.csv`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `pull_requests/pr-1464-review.md`
- `tests/test_trending_terms.py`
- `web_app/e2e/trending-terms.check.mjs`
- `web_app/src/api/trendingTerms.ts`
- `web_app/src/components/trends/TrendingTermsRow.test.tsx`
- `web_app/src/components/trends/TrendingTermsRow.tsx`
- `web_app/src/pages/BrowseAllTopics.tsx`
- `web_app/src/utils/trendingTerms.test.ts`
- `web_app/src/utils/trendingTerms.ts`
- `web_docs/docs/development/trending-terms-and-hot-words.md`

## CI Status

See the PR checks on `210e93300ec1`.

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
