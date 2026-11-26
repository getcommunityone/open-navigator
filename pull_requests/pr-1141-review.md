---
pr: 1141
branch: feat/1125-topic-story-captions
title: "feat(stories): one conclusion title per topic and scope, from the record: hates, divided, state gap, volume (#1125)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 4740ce99fe5af8c9e385356b9d587fb23ea4a0e8
verdict: approve
---

# PR Review: feat(stories): one conclusion title per topic and scope, from the record: hates, divided, state gap, volume (#1125)

## Summary

Automated review (#648) for PR #1141 on `feat/1125-topic-story-captions`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/topic_caption_facts.py`
- `tests/test_api_topic_caption_facts.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `4740ce99fe5a`.

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
