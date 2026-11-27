---
pr: 1212
branch: fix/1206-home-title-place-control
title: "fix(home): the place in the home story title is a subtle inline place control again"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 8cfd036c4acab6ee82d36c76da3d15b452625f99
verdict: approve
---

# PR Review: fix(home): the place in the home story title is a subtle inline place control again

## Summary

Automated review (#648) for PR #1212 on `fix/1206-home-title-place-control`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeStoryTitle.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/stance/PlaceControl.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/styles/home-place.css`
- `web_app/src/utils/captionPlace.test.ts`
- `web_app/src/utils/captionPlace.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `8cfd036c4aca`.

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
