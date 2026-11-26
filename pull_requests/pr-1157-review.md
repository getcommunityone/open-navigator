---
pr: 1157
branch: fix/1155-topic-company-proximity
title: "fix(topics): count a seeded-topic company only near the topic's own words"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 013a9930833c72975883143bc90cf6ca7d08c693
verdict: approve
---

# PR Review: fix(topics): count a seeded-topic company only near the topic's own words

## Summary

Automated review (#648) for PR #1157 on `fix/1155-topic-company-proximity`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/models/marts/topic_company_mention.sql`
- `web_docs/docs/development/topic-companies.md`

## CI Status

See the PR checks on `013a9930833c`.

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
