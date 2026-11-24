---
pr: 880
branch: feat/879-chat-close-button
title: "feat(web_app): add a close button to the chat panel"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 3ed9fed58dd1ba10fc2b0a462c25e302dc6f67f4
verdict: approve-with-nits
---

# PR Review: feat(web_app): add a close button to the chat panel

## Summary

Adds a close button to the chat panel. Closing goes back to the page the visitor came from, or home when the chat
was the first page opened; Escape does the same unless a message is being typed. Small, unit-tested for the
destination rule, and checked in a browser.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/src/pages/MeetingChat.tsx`
- `web_app/src/utils/contact.test.ts`
- `web_app/src/utils/contact.ts`
- `web_docs/docs/development/meeting-chat-model.md`

## CI Status

See the PR checks on `3ed9fed58dd1`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean.

## Strengths

- Escape does not discard a draft message.
- The destination rule is a pure function with a test, and matches the back rule other pages use.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- The button's look at phone width was not checked.
- Escape is handled on the window, so a dialog opened over the chat in future would need to stop the event first.

## Verdict

**approve-with-nits**
