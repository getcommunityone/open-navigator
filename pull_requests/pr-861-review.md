---
pr: 861
branch: feat/860-chat-and-contact
title: "feat(web_app): combine Chat and Contact in the header"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: a614ee4c16370fa80e21c70eb7bb6a56b63355a6
verdict: approve-with-nits
---

# PR Review: feat(web_app): combine Chat and Contact in the header

## Summary

Merges the header's "Chat" and "Contact" items into one, "Chat & Contact", and puts a contact strip with an email
link at the top of the chat panel. The contact address moves to one shared constant. Small; checked in a browser at
two widths.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/pages/MeetingChat.tsx`
- `web_app/src/pages/Support.tsx`
- `web_app/src/utils/contact.test.ts`
- `web_app/src/utils/contact.ts`
- `web_docs/docs/development/meeting-chat-model.md`

## CI Status

See the PR checks on `a614ee4c1637`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. The email address was already public on the Contact page; it is moved, not added.

## Strengths

- One address constant now feeds both places, so they cannot drift apart.
- `/support` is kept, so existing links (including the Not Found page's) still work.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- At 400 px the strip takes two lines plus the button row, which shortens the message area a little.
- The mobile menu was not opened in the browser check; it renders from the same list, so the item should match.

## Verdict

**approve-with-nits**
