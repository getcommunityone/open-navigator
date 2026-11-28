---
pr: 1475
issue: 1445
branch: feat/1445-bodies-api
title: "feat(api): jurisdiction bodies and body detail endpoints"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1475 review

Reviewed against `.claude/review-rubric.md`.

## Summary

Two read-only endpoints over the new public marts, the publish-list entries and their ODCS contracts. Verified against
the local warehouse through a branch API (Tuscaloosa returns 19 bodies; the council has the mayor and six seated
members with districts, the District 5 vacancy and four recent speakers with moment links). Approve with nits.

## Scans

- Secrets: clean. Fabricated data: clean (no defaults or fallback numbers; empty lists and 404s instead).
- Personal data: officials in their public role; `public.body_membership` carries no contact fields; no residents.
- Destructive data changes: none (views added to the publish list).

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- Large Legistar places return every body with its members in one response (Milwaukee has ~190 bodies). Fine for now;
  a `limit` on bodies could follow if the payload matters on phones.
- Routes live in `api/main.py`, so `api.types.ts` (from `api.app`) does not cover them, same as the neighbouring
  jurisdiction routes.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, naming | Yes | #1445 |
| API reads `public` only | Yes | |
| OpenTelemetry spans | Yes | one span per endpoint |
| Data contracts current | Yes | `models.odcs --check` passes |
| Dates as ISO strings | Yes | real `date` columns |

## Test Coverage

pytest 5 passed with a fake pool (geoid lookup, 404, member ordering and counting, body detail, `limit` validation,
route registration). Manual check against the local warehouse.

## Verdict

approve-with-nits.
