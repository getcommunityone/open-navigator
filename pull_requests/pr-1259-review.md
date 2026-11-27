---
pr: 1259
branch: fix/1258-publish-meeting-video-kind
title: "fix(data): keep meeting_video_kind in the production Neon sync"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 975f4bfa0f72690850266d4a506e3462e7316f91
verdict: approve
---

# PR Review: fix(data): keep meeting_video_kind in the production Neon sync

## Summary

Automated review (#648) for PR #1259 on `fix/1258-publish-meeting-video-kind`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `web_docs/docs/development/neon-serving-scope.md`

## CI Status

See the PR checks on `975f4bfa0f72`.

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
