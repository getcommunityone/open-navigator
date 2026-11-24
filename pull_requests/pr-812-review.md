---
pr: 812
branch: fix/808-browse-topics-empty-state
title: "fix(web_app): show topic load failures and empty states; add default curated topics"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 26574f07f1b74ed5f95370a8dd54847a1abaadbe
verdict: approve
---

# PR Review: fix(web_app): show topic load failures and empty states; add default curated topics

## Summary

Automated review (#648) for PR #812 on `fix/808-browse-topics-empty-state`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topics.py`
- `dbt_project/seeds/curated_topics.csv`
- `tests/test_api_topics.py`
- `web_app/src/pages/BrowseTopics.tsx`
- `web_app/src/pages/UnifiedSearch.tsx`
- `web_docs/docs/development/browse-topics-catalog.md`

## CI Status

See the PR checks on `26574f07f1b7`.

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
