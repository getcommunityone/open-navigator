---
pr: 1459
issue: 1442
branch: feat/1442-governing-body
title: "feat(dbt): governing_body and meeting_body from meeting titles, platform bodies and rosters"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1459 review

Reviewed against `.claude/review-rubric.md`.

## Summary

Adds the body layer: a seed of ordered title patterns, a cleaning macro, `int_meeting_body__matched`, and the marts
`governing_body` and `meeting_body` with enforced PK/FK contracts. It works on the local warehouse (72% of meetings
matched, Tuscaloosa's council, P&Z, BZA, HPC and committees all present) and the SQL and Python twins agree on the
example seed and on 41k real titles. Approve with nits.

## Scans

- Secrets: clean. Fabricated data: clean (counts are computed from meetings; a roster-only body shows 0 meetings, not
  a guess). Personal data: clean (no people in these marts). Destructive data changes: none (new tables only).

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- `governing_body`: a body renamed over time appears twice (Tuscaloosa "Public Projects Committee" in 2020-2026
  agendas and "Projects Committee" on YouTube since 2024; "Planning Commission"/"Zoning Commission" in agendas vs
  "Planning and Zoning Commission"). Honest to the sources, but a per-place alias seed would merge them. Follow-up
  noted in the decision page.
- `meeting_count` folds a council meeting and its pre-council briefing on the same date into one date; documented.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts, branch/PR naming | Yes | #1442, `feat/1442-...`, `Closes #1442` |
| Transformations in dbt | Yes | Python twin is for tests only; documented why |
| Explicit PK and FKs | Yes | contracts enforced; relationships test |
| No dim_/fact_ names | Yes | |
| Docs with the change | Yes | `governing-bodies.md` |
| Calendar years / dates | Yes | real `date` columns |

## Test Coverage

pytest 51 passed (example seed, Tuscaloosa titles, county-in-city skip, school district board, people named in
titles, helpers, seed ordering). dbt build + tests PASS=26 locally. CI on the head commit: see the PR checks.

## Verdict

approve-with-nits.
