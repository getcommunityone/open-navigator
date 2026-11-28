---
pr: 1482
branch: feat/1446-who-governs-ui
title: "feat(web): Who governs and Officials heard most recently on the place page, body page"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 9241a6d0b7b59b98c48da2ca7eeb56276e2f7051
verdict: approve
---

# PR Review: feat(web): Who governs and Officials heard most recently on the place page, body page

## Summary

Automated review (#648) for PR #1482 on `feat/1446-who-governs-ui`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/who-governs.check.mjs`
- `web_app/src/App.tsx`
- `web_app/src/components/bodies/PlaceGovernance.tsx`
- `web_app/src/components/bodies/WhoGoverns.test.tsx`
- `web_app/src/components/bodies/WhoGoverns.tsx`
- `web_app/src/lib/governingBodies.test.ts`
- `web_app/src/lib/governingBodies.ts`
- `web_app/src/lib/pageClose.ts`
- `web_app/src/pages/BodyDetail.tsx`
- `web_app/src/pages/MeetingDocuments.tsx`
- `web_docs/docs/development/governing-bodies.md`

## CI Status

See the PR checks on `9241a6d0b7b5`.

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
