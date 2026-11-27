---
pr: 1185
branch: fix/1182-story-start-next-map-title
title: "fix(stories): topic-named Start and Next story on every story, and the title says what the map shows"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 372a9619b39d1b13a3c34b63ebc66f67881d8a04
verdict: approve
---

# PR Review: fix(stories): topic-named Start and Next story on every story, and the title says what the map shows

## Summary

Automated review (#648) for PR #1185 on `fix/1182-story-start-next-map-title`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `tests/test_api_topic_caption_facts.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/styles/story-actions.css`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/development/story-statements-where-you-sit.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `372a9619b39d`.

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
