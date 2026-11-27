---
pr: 1317
branch: fix/1316-state-never-national
title: "fix(stories): a state-scoped story never shows America's title or the national map"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 75f33ac46cbefe0f279deed09e3014cd264baa7e
verdict: approve
---

# PR Review: fix(stories): a state-scoped story never shows America's title or the national map

## Summary

Automated review (#648) for PR #1317 on `fix/1316-state-never-national`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `pull_requests/assets/1316/after-laptop.png`
- `pull_requests/assets/1316/after-phone.png`
- `pull_requests/assets/1316/before-laptop.png`
- `pull_requests/assets/1316/before-phone.png`
- `pull_requests/pr-1317-review.md`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/storyCaptionPosition.test.ts`
- `web_app/src/utils/storyCaptionStateScope.test.ts`
- `web_docs/docs/development/story-captions.md`

## CI Status

See the PR checks on `75f33ac46cbe`.

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
