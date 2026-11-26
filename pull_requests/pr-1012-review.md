---
pr: 1012
branch: fix/1011-chat-answer-format
title: "fix(web_app): Ask meetings answers render bold, bullets and meeting links; prompts ask for brevity"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 8f7b4de1b1bd32137089c488b086fe9daa9cb3dd
verdict: approve
---

# PR Review: fix(web_app): Ask meetings answers render bold, bullets and meeting links; prompts ask for brevity

## Summary

Automated review (#648) for PR #1012 on `fix/1011-chat-answer-format`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/chat_meetings.py`
- `web_app/src/components/meeting-chat/ChatMarkdown.test.tsx`
- `web_app/src/components/meeting-chat/ChatMarkdown.tsx`
- `web_app/src/components/meeting-chat/MeetingChatThread.tsx`

## CI Status

See the PR checks on `8f7b4de1b1bd`.

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
