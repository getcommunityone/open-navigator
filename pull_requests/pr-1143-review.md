---
pr: 1143
branch: feat/1133-all-topic-stories-live
title: "feat(stories): every topic with meetings gets a live story and tile instead of Coming soon (#1133)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 40813ed71fe044635057ccffd960a747aea16e1f
verdict: approve
---

# PR Review: feat(stories): every topic with meetings gets a live story and tile instead of Coming soon (#1133)

## Summary

Automated review (#648) for PR #1143 on `feat/1133-all-topic-stories-live`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `web_app/src/App.tsx`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/hooks/useTopicStories.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/homeTopicTiles.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/topicStories.test.ts`
- `web_app/src/utils/topicStories.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `40813ed71fe0`.

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
