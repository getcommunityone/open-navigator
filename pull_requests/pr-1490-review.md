---
pr: 1490
issue: 1486
branch: perf/1486-meeting-body-slim
title: "perf(neon): slim public.meeting_body; release battery-storage speaker sides"
reviewed_at: 2026-11-28
reviewer: data-dbt-specialist
verdict: approve-with-nits
---

# PR #1490 review

Reviewed against `.claude/review-rubric.md`.

## Summary

Publishes `public.meeting_body` as a slim projection (latest 25 per body within 12 months, always the latest 1, 7
columns), adds the four body relations to `CIVIC_SERVING`, caps the body API at 25, and releases battery-storage from
`HELD`. Gold keeps the full mart. Nothing was written to Neon.

## Scans

- Secrets: clean. Fabricated data: clean (every row is a gold row; totals still come from `governing_body`). Personal
  data: clean (meeting titles and links only). Destructive data changes: none (public projection only).

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- The 3 MB target is not met: 31,717 rows, about 8.9 MB local with indexes (gold 83 MB). One row per body alone is
  about 3 MB (10,021 bodies). A 6-month window gives about 5 MB. Owner's call.
- The "showing the latest 25 of N" line is frontend work, handed back (`BodyDetail.tsx`).

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts, branch/PR naming | Yes | #1486 |
| Transformations in dbt | Yes | projection lives in `publish_public_serving` |
| Explicit PK and FKs | Yes | gold contract unchanged; public table gets a unique index on `meeting_body_id` |
| Docs with the change | Yes | `governing-bodies.md` |

## Test Coverage

`tests/test_api_governing_bodies.py` 5 passed; `packages/llm/tests/test_speaker_stance.py` 20 passed. Projection SQL
run against the local warehouse (31,717 rows).

## Verdict

approve-with-nits.
