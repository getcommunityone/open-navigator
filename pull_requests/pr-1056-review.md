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

## Agent review

- Issue and branch: feat/1052-topic-companies, Closes #1052; pickleball scope added by a dated issue comment.
- Scans: no secrets, no personal data, no deletions. No fabricated data: counts are distinct meetings/decisions from topic_company_mention; every row needs a <mark> excerpt; companies never named in scope get no number.
- Keys: topic_company PK + FK to civicsearch_topic; topic_company_mention PK + FK to topic_company (contract enforced).
- Correctness: seeded topics are gated to topic-tagged meetings/decisions; surname-like brands need product phrases; data center names need a data-center phrase within 250 characters; content_tsv (stored, indexed) replaces per-row to_tsvector (15 min -> 38 s). API binds topic/state/city as parameters; missing tables return an empty list; other errors 503. Scope label in the panel heading matches the page filter.
- Checks: 4 API tests pass; ruff clean on new files; tsc clean; browser check at /?state=AL. Docs: topic-companies.md.

No blocking findings.
