---
pr: 842
branch: fix/840-meeting-type-unpublished
title: "fix(api): answer with a null meeting type when its relation is not published"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: c012fa85975ff9937c982ee9562522c21c3d8eba
verdict: approve-with-nits
---

# PR Review: fix(api): answer with a null meeting type when its relation is not published

## Summary

Three endpoints (`GET /api/decisions`, `GET /api/decisions/{id}`, `GET /api/meetings/{id}`) failed on any API that
reads `public`, because #805 made them read a relation that only exists in `gold`. The PR checks once whether the
relation resolves and selects `NULL` when it doesn't. Small and tested at the unit level. It was not run against a
warehouse: the fix rests on the owner's log line and on reading the three queries.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `api/meeting_type.py`
- `api/routes/decision_browse.py`
- `api/routes/decisions.py`
- `api/routes/meetings.py`
- `tests/test_meeting_type_797.py`
- `web_docs/docs/development/meeting-type-label.md`

## CI Status

See the PR checks on `c012fa85975f`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. A missing type is returned as `null`, never guessed.

## Strengths

- The relation name now lives in one constant and the three routes build their column from the helpers, so they
  cannot drift apart again.
- A missing relation is re-checked after five minutes, so publishing it later (#841) needs no restart.
- The doc page that wrongly said the column reaches `public` is corrected in the same PR.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not run end to end. The container has no `asyncpg` and cannot reach the warehouse, so the route modules were
  parsed but not imported, and no request was made. The owner should confirm on their machine that
  `GET /api/decisions?limit=1` answers after pulling.

### 🔵 Nit (Minor)

- A true answer is remembered for the life of the process. If the relation is dropped while the API runs, the three
  endpoints fail until restart. That needs a deliberate schema change, so it is acceptable.
- The check costs one extra round trip per request while the relation is missing and the five minutes have passed;
  otherwise none.

## Verdict

**approve-with-nits**
