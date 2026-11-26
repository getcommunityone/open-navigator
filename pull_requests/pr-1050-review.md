---
pr: 1050
branch: feat/1049-chat-throttle-per-user
title: "feat(api): throttle meeting chat per signed-in user, per IP for guests, with daily caps"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: c3a49c47f8abda2608c1bf0ec316d31847b722c0
verdict: approve
---

# PR Review: feat(api): throttle meeting chat per signed-in user, per IP for guests, with daily caps

## Summary

Automated review (#648) for PR #1050 on `feat/1049-chat-throttle-per-user`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/chat_meetings.py`
- `tests/test_chat_meetings.py`
- `web_app/src/components/meeting-chat/MeetingChatRuntime.tsx`
- `web_docs/docs/development/meeting-chat-model.md`

## CI Status

See the PR checks on `c3a49c47f8ab`.

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

## Agent review

- **Issue and branch:** `feat/1049-chat-throttle-per-user`, `Closes #1049`. The sign-in change is recorded on the issue
  as a dated comment; the original text is unchanged.
- **Scans:** no secrets (tests mint tokens with the app's own helper at run time), no fabricated data, no personal data
  stored (the throttle holds `user:<id>` counters in memory only; telemetry drops the id), no data changes.
- **Correctness:**
  - `_visitor_key` raises 401 before `_check_rate_limit`, `_check_spend_cap` or any query, so a guest can't spend.
  - `decode_access_token` raises on a bad or expired token; that is caught and treated as not signed in, so the result is
    401, not 500.
  - `login(provider, returnTo)` only passes a `returnTo` on this origin, and the API's `is_safe_redirect` checks again;
    the OAuth success redirect appends `&token=` when the URL already has a query, so the chat's `?state=` survives.
  - The chat page shows the sign-in panel only after auth has loaded, so a signed-in user doesn't see it flash.
- **Checks:** chat tests 26 passed; tsc clean. Required CI runs on the head commit.
- **Docs:** `meeting-chat-model.md` updated.

No blocking findings.
