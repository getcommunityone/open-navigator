---
pr: 1196
branch: fix/1194-publish-recorded-meeting-year
title: "fix(data): publish recorded_meeting_year to production Neon"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 716e56c9847aa0aedbc9b00d03fb7a93f96312e8
verdict: approve
---

# PR Review: fix(data): publish recorded_meeting_year to production Neon

## Summary

Automated review (#648) for PR #1196 on `fix/1194-publish-recorded-meeting-year`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `web_docs/docs/development/neon-serving-scope.md`

## CI Status

See the PR checks on `716e56c9847a`.

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
