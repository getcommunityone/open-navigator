---
pr: 1160
branch: feat/1127-topic-stance-map
title: "feat(stories): four-colour box map on every topic story from the AI reading"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: ce70bc2498ca6e43960b2815c602f8f6539e5651
verdict: approve
---

# PR Review: feat(stories): four-colour box map on every topic story from the AI reading

## Summary

Automated review (#648) for PR #1160 on `feat/1127-topic-stance-map`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topics.py`
- `tests/test_api_topic_state_map.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/topicStance.test.ts`
- `web_app/src/utils/topicStance.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `ce70bc2498ca`.

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
