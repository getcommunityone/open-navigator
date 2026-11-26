---
pr: 917
branch: fix/916-chat-failure-reporting
title: "fix(chat): say why the chat cannot answer, on the page and in the log"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: e509d6766a46d11dcea254b89f2c3ec69ec8e208
verdict: approve-with-nits
---

# PR Review: fix(chat): say why the chat cannot answer, on the page and in the log

## Summary

Makes the cause of a failed chat visible. A missing provider key answers 503 'Chat is not set up on this site yet.' before any model call and logs the provider and the missing variable name; a failed model call logs provider, model, exception type and status; GET /api/chat/status reports provider, model and whether the key is set. The page shows the server's own reason, with separate wording for a timeout and for no connection.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `api/routes/chat_meetings.py`
- `tests/test_chat_meetings.py`
- `web_app/src/components/meeting-chat/MeetingChatRuntime.tsx`
- `web_app/src/utils/chatError.test.ts`
- `web_app/src/utils/chatError.ts`
- `web_docs/docs/deployment/huggingface-spaces.md`
- `web_docs/docs/development/meeting-chat-model.md`

## CI Status

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- The live cause is not confirmed; the status endpoint settles it after the next deploy.
- The status endpoint is public. It exposes the provider and model name and a boolean, no secret; acceptable, but worth knowing.
- Error wording was not viewed in a browser at phone size; it is text inside the existing bubble.
- npm run gen:api could not run in the review container; CI runs it.

## Verdict

**approve-with-nits**
