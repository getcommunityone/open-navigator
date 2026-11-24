---
pr: 817
branch: fix/816-topic-meetings-503
title: "fix(api): answer 503 when a topic's meetings query fails"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve
---

# PR Review: fix(api): answer 503 when a topic's meetings query fails

## Summary
A three-line behaviour change: `GET /api/topics/{topic_id}/meetings` now answers 503 when its query fails instead of
`200` with `total: 0`. It mirrors the fix already merged for the topic list (#812), has a regression test, and needs no
frontend change because the one caller already distinguishes an error from an empty list. Approve.

## Scope of Change
- Files changed: 3 (excluding this review)
- Areas touched: api / tests / web_docs
- Commits: `7898a7ac` fix(api): answer 503 when a topic's meetings query fails
- Range reviewed: `origin/main...origin/fix/816-topic-meetings-503`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. The change removes a case where a failure was presented as a real zero.

## Strengths
- The exception is still logged and recorded on the span before the 503.
- The test replaces `fetchval` with one that raises, so it fails on `main` (which returned 200).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `TopicMeetingList.tsx` shows a fixed error sentence rather than the API's `detail`. Fine: the fixed sentence says the
  same thing.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #816 with the four parts; branch `fix/816-topic-meetings-503`; `Closes #816` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | A failure is no longer shown as "0 meetings" |
| Docs | Yes | `web_docs/docs/development/browse-topics-catalog.md` |
| Telemetry and logging | Yes | Span and log unchanged |
| Tests | Yes | Regression test added |

## Test Coverage
`pytest tests/test_api_topics.py`: 13 passed. The only caller (`web_app/src/components/TopicMeetingList.tsx`) was
traced by reading: its `isError` branch renders the error state.

## Verdict
approve.
