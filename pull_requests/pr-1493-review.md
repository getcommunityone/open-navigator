---
pr: 1493
branch: fix/1401-curated-topics-seed
title: "fix(topics): align curated_topics seed with warehouse IDs 100001-100020 and 100101-100111"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: fca6ce61a379d1acae788be59a34ef676aca86e2
verdict: approve
---

# PR Review: fix(topics): align curated_topics seed with warehouse IDs 100001-100020 and 100101-100111

## Summary

Automated review (#648) for PR #1493 on `fix/1401-curated-topics-seed`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/seeds/curated_topics.csv`
- `tests/test_curated_topics_seed.py`
- `web_docs/docs/development/speaker-stance-classifier.md`
- `web_docs/docs/development/topic-place-rankings.md`

## CI Status

See the PR checks on `fca6ce61a379`.

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
