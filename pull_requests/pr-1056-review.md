---
pr: 1056
branch: feat/1052-topic-companies
title: "feat(topics): Companies named for every topic (data centers, plate readers, guns, pickleball, rentals)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: cb1d45a53b81269fed4031f299ae98072436f39f
verdict: approve
---

# PR Review: feat(topics): Companies named for every topic (data centers, plate readers, guns, pickleball, rentals)

## Summary

Automated review (#648) for PR #1056 on `feat/1052-topic-companies`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/topic_companies.py`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_topic_company.yml`
- `dbt_project/models/marts/topic_company.sql`
- `dbt_project/models/marts/topic_company_mention.sql`
- `dbt_project/seeds/topic_companies.csv`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `tests/test_api_topic_companies.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/components/home/TopicCompaniesPanel.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_docs/docs/development/topic-companies.md`

## CI Status

See the PR checks on `cb1d45a53b81`.

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
