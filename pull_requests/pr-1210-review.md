---
pr: 1210
branch: fix/1203-all-data-stories-index
title: "fix(stories): /stories lists every data story for the place in scope"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 0c8f55db34181bd3c1db152f81578717dbbc5f56
verdict: approve
---

# PR Review: fix(stories): /stories lists every data story for the place in scope

## Summary

Automated review (#648) for PR #1210 on `fix/1203-all-data-stories-index`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/storyIndex.test.ts`
- `web_app/src/utils/storyIndex.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `0c8f55db3418`.

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
