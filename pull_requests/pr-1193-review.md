---
pr: 1193
branch: fix/1190-plain-stance-wording
title: "fix(stories): say \"the public mostly opposed\" instead of \"leaned against\""
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 21ed3eca8a8f5494bfdc221b9674ee072de0837d
verdict: approve
---

# PR Review: fix(stories): say "the public mostly opposed" instead of "leaned against"

## Summary

Automated review (#648) for PR #1193 on `fix/1190-plain-stance-wording`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/topic_caption_facts.py`
- `api/routes/topics.py`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/home/storyColors.test.ts`
- `web_app/src/components/home/storyColors.ts`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/heroPoints.test.ts`
- `web_app/src/utils/heroPoints.ts`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/storyConclusion.test.ts`
- `web_app/src/utils/topicStance.test.ts`
- `web_app/src/utils/topicStance.ts`
- `web_app/src/utils/unitMatrix.test.ts`
- `web_app/src/utils/unitMatrix.ts`
- `web_docs/docs/development/data-center-meeting-lean.md`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/development/topic-meeting-lean.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `21ed3eca8a8f`.

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
