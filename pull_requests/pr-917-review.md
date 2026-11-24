---
pr: 917
branch: fix/916-chat-failure-reporting
title: "fix(chat): say why the chat cannot answer, on the page and in the log"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: e509d6766a46d11dcea254b89f2c3ec69ec8e208
verdict: approve
---

# PR Review: fix(chat): say why the chat cannot answer, on the page and in the log

## Summary

Automated review (#648) for PR #917 on `fix/916-chat-failure-reporting`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/chat_meetings.py`
- `tests/test_chat_meetings.py`
- `web_app/src/components/meeting-chat/MeetingChatRuntime.tsx`
- `web_app/src/utils/chatError.test.ts`
- `web_app/src/utils/chatError.ts`
- `web_docs/docs/deployment/huggingface-spaces.md`
- `web_docs/docs/development/meeting-chat-model.md`

## CI Status

See the PR checks on `e509d6766a46`.

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
