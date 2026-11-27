---
pr: 1312
branch: fix/1309-county-map-fit
title: "fix(stories): state county dot map fits the screen on phones and laptops"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 173bcf78aec110c49dadb817c4f1c907f428bdf5
verdict: approve
---

# PR Review: fix(stories): state county dot map fits the screen on phones and laptops

## Summary

Automated review (#648) for PR #1312 on `fix/1309-county-map-fit`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `pull_requests/assets/1309/after-TN-laptop1366.png`
- `pull_requests/assets/1309/after-laptop1366.png`
- `pull_requests/assets/1309/after-laptop1440.png`
- `pull_requests/assets/1309/after-phone.png`
- `pull_requests/assets/1309/before-laptop1366.png`
- `pull_requests/assets/1309/before-laptop1440.png`
- `pull_requests/assets/1309/before-phone.png`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/mapFit.test.ts`
- `web_app/src/utils/mapFit.ts`
- `web_docs/docs/development/story-drill-box-transition.md`

## CI Status

See the PR checks on `173bcf78aec1`.

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
