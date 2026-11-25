---
pr: 951
branch: fix/950-stories-overview-first
title: "fix(web): open Data Stories on overview, not the question"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 66128e3f539219b7ed88043ab5a2016931c24729
verdict: approve
---

# PR Review: fix(web): open Data Stories on overview, not the question

## Summary

Automated review (#648) for PR #951 on `fix/950-stories-overview-first`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `66128e3f5392`.

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
