---
pr: 1352
branch: feat/1343-browse-all-topics-yoy
title: "feat(topics): browse all topics \u2014 one animated year-over-year dumbbell of every main topic"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 59769c31ef964fe3e5c008109da8f7c4634370da
verdict: approve
---

# PR Review: feat(topics): browse all topics — one animated year-over-year dumbbell of every main topic

## Summary

Automated review (#648) for PR #1352 on `feat/1343-browse-all-topics-yoy`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/topic_yoy.py`
- `tests/test_api_topic_yoy.py`
- `web_app/src/App.tsx`
- `web_app/src/api/topicsYoy.ts`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/components/stance/DumbbellRows.tsx`
- `web_app/src/components/stance/DumbbellRowsLinks.test.tsx`
- `web_app/src/components/stance/storyCharts.css`
- `web_app/src/pages/BrowseAllTopics.tsx`
- `web_app/src/pages/BrowseTopics.tsx`
- `web_app/src/utils/topicsYoy.test.ts`
- `web_app/src/utils/topicsYoy.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `59769c31ef96`.

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
