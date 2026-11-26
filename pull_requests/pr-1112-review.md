---
pr: 1112
branch: feat/1108-quote-card-format
title: "feat(stories): quote popups in the owner's card format: recording thumbnail, big quote, speaker row (real data only)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: b1984ee51c1925ab3dabed8600bdaa6dd4c6b86e
verdict: approve
---

# PR Review: feat(stories): quote popups in the owner's card format: recording thumbnail, big quote, speaker row (real data only)

## Summary

Automated review (#648) for PR #1112 on `feat/1108-quote-card-format`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/home/storyColors.ts`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/MeetingVideoModal.tsx`
- `web_app/src/components/stance/QuoteCard.css`
- `web_app/src/components/stance/QuoteCard.test.tsx`
- `web_app/src/components/stance/QuoteCard.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/components/stance/quoteCardUtils.test.ts`
- `web_app/src/components/stance/quoteCardUtils.ts`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/stance.css`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `b1984ee51c19`.

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
