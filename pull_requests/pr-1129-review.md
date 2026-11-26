---
pr: 1129
branch: feat/1124-story-card-summary-speaker
title: "feat(stories): meeting cards show the AI summary, a link to the meeting analysis, and the speaker as First L. when on record (#1124)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 324d4f8485634a73136ee5e91def094cdf2ca0af
verdict: approve
---

# PR Review: feat(stories): meeting cards show the AI summary, a link to the meeting analysis, and the speaker as First L. when on record (#1124)

## Summary

Automated review (#648) for PR #1129 on `feat/1124-story-card-summary-speaker`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `tests/test_api_data_center_meeting_mentions.py`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/QuoteCard.css`
- `web_app/src/components/stance/QuoteCard.test.tsx`
- `web_app/src/components/stance/QuoteCard.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/components/stance/quoteCardUtils.test.ts`
- `web_app/src/components/stance/quoteCardUtils.ts`
- `web_app/src/lib/api.types.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `324d4f848563`.

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
