---
pr: 973
branch: feat/972-meeting-dot-video
title: "feat(web_app): meeting dots preview a thumbnail and play the recording in a modal"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 3bdb8964bd59edd912e1b7c09f44947c7333d78b
verdict: approve
---

# PR Review: feat(web_app): meeting dots preview a thumbnail and play the recording in a modal

## Summary

Automated review (#648) for PR #973 on `feat/972-meeting-dot-video`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/matrix/Tooltip.tsx`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/MeetingDots.test.tsx`
- `web_app/src/components/stance/MeetingVideoModal.tsx`
- `web_app/src/lib/youtubeEmbed.test.ts`
- `web_app/src/lib/youtubeEmbed.ts`
- `web_app/src/styles/folio.css`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `3bdb8964bd59`.

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
