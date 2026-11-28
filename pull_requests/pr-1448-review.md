---
pr: 1448
branch: feat/1416-hot-topic-pills
title: "feat(home): hot and trending topic pills with box-flight topic and place switching"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 464ac894b10b82d4ed35df8575aa959f7f436864
verdict: approve
---

# PR Review: feat(home): hot and trending topic pills with box-flight topic and place switching

## Summary

Automated review (#648) for PR #1448 on `feat/1416-hot-topic-pills`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/hero-topic-switch.check.mjs`
- `web_app/src/components/home/HomeCandidateTopicCard.tsx`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeStoryTitle.tsx`
- `web_app/src/components/home/HomeTopicBar.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/stance/BoxFlightProvider.tsx`
- `web_app/src/components/stance/storyCharts.css`
- `web_app/src/hooks/useHotTopics.ts`
- `web_app/src/styles/home-topic-bar.css`
- `web_app/src/utils/boxFlight.ts`
- `web_app/src/utils/heroPrefetch.ts`
- `web_app/src/utils/hotTopics.test.ts`
- `web_app/src/utils/hotTopics.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `464ac894b10b`.

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
