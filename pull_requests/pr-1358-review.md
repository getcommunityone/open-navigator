---
pr: 1358
branch: fix/1357-map-hover-state-meetings
title: "fix(stories): hovering different boxes in a state switches the meeting panel"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 6097c7b1094da73671df197c40ed6ddfa6f4cb72
verdict: approve
---

# PR Review: fix(stories): hovering different boxes in a state switches the meeting panel

## Summary

Automated review (#648) for PR #1358 on `fix/1357-map-hover-state-meetings`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topics.py`
- `tests/test_api_story_map_quotes.py`
- `web_app/e2e/map-taps.check.mjs`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/mapQuote.test.ts`
- `web_app/src/utils/mapQuote.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `6097c7b1094d`.

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
