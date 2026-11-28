---
pr: 1408
branch: feat/1407-most-heated-topics
title: "feat(topics): Most heated sort on Browse all topics from classifier speaker heat"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 09b3ec1f1174c883554a06155bbe6817162b3844
verdict: approve
---

# PR Review: feat(topics): Most heated sort on Browse all topics from classifier speaker heat

## Summary

Automated review (#648) for PR #1408 on `feat/1407-most-heated-topics`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_yoy.py`
- `tests/test_api_topic_yoy.py`
- `web_app/src/api/topicsYoy.ts`
- `web_app/src/pages/BrowseAllTopics.tsx`
- `web_app/src/utils/topicsYoy.test.ts`
- `web_app/src/utils/topicsYoy.ts`
- `web_docs/docs/development/speaker-stance-classifier.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `09b3ec1f1174`.

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
