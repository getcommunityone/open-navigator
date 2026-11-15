---
pr: 385
branch: feat/250-agenda-matches
title: "feat(dc): DC-4.2 data center items on meeting agendas, upcoming first, with quoted evidence"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: DC-4.2 agenda items (#385)

## Summary
Finds agendas that mention a data center (`event_meeting_document`, `document_type = 'agenda'`), keeps a verbatim highlighted excerpt, flags a zoning, land-use, tax-incentive or utility word near the mention, links a tracked site the agenda names, and shows upcoming meetings first on `/data-centers`. It meets #250's "Done when": a site with a zoning or utility item on a future agenda surfaces before the vote, naming the meeting and date. Coverage is limited to agendas with extracted text (mostly Tuscaloosa today). Approve with nits.

## Scope of Change
- dbt: mart `data_center_agenda_item` (enforced contract, FKs to `event_meeting_document`, `jurisdictions`, `data_center_site`), ODCS generated, served list and state filter.
- API: `GET /api/data-centers/agenda-items` (+ 6 tests).
- Web: "On the agenda" section (`highlightSnippet` for the evidence), client, `api.types.ts` (additions only).
- Docs: `data-center-agenda-items.md`.

## CI Status
Checked on the head commit before merge; see the PR's Checks tab.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: none.
- Fabricated data: none. Evidence is `ts_headline` over the agenda's own text, and rows without a highlighted excerpt are dropped; "upcoming" is computed at request time.
- Personal data: none beyond public agenda text.
- Destructive changes: none.

## Strengths
- Follows the match-evidence rule end to end: backend `ts_headline` with `<mark>`, rendered by `highlightSnippet` (React-escaped).
- Upcoming vs past is computed in the API, so the materialized table can't go stale on that point.
- The scope label and query move together; the city matches the jurisdiction name, as the browse routes do.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Grain is one row per agenda, not per agenda item, so a long agenda with two data center items shows as one tile (with up to two excerpts). Splitting agendas into items is CORE work, so it stays out of this PR.
- "tax" and "power" are broad context words. The 250-character window keeps them close to the mention, and the quote lets a reader judge.
- Only agendas with extracted text are searched (~497 documents, mostly Tuscaloosa). More cities depend on CORE-3.2 adapters.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first, Contract before first commit (+ dated note on the 250 window) | ✅ #250 |
| Branch `<type>/<issue>-<slug>`, `Closes #250` | ✅ |
| Conventional Commits | ✅ |
| Transformations in dbt | ✅ matching and evidence in SQL |
| PK and FKs on the public relation | ✅ |
| Match evidence on filtered tiles | ✅ |
| Scope label rule | ✅ |
| No fabricated data | ✅ |
| Decisions written down | ✅ `data-center-agenda-items.md` |

## Test Coverage
- API: 6 tests (city scope and params, `when` filters items not counts, ordering, 422, missing mart, 500).
- dbt and SQL: compiled mart run on PostgreSQL against stub agendas. A rezoning item linked to the right state's site; a distant mention untagged; minutes and unrelated agendas excluded; an unknown jurisdiction left null. The API's own SQL returned upcoming-first ordering and whole-scope counts.
- Web: `tsc` and eslint clean.
- Not covered: the real Tuscaloosa agendas (warehouse not reachable from the sandbox).

## Verdict
**approve-with-nits.**
