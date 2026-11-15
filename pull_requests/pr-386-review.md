---
pr: 386
branch: feat/251-concern-ranking
title: "feat(dc): DC-4.3 rank data center agenda items by what residents object to locally"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: DC-4.3 local concern ranking (#386)

## Summary
Measures what residents object to in their own meetings (`event_decision` counter-views, sorted into seven concerns in dbt), stores it per jurisdiction and nationally in `area_concern`, tags data center agenda items with the concerns near the mention, and ranks items that match the area's dominant concern first. It meets #251's first "Done when": where local concern data exists, a matching item ranks above one that doesn't. The second line (water ≈ 41% nationally) has no source, so it is computed from records rather than hard-coded, and the Contract says so. Approve with nits.

## Scope of Change
- dbt: `local_concern_patterns` macro; mart `area_concern` (enforced contract, ODCS); `data_center_agenda_item.concerns` (additive); served list.
- API: `GET /api/data-centers/concerns` (+ 4 tests); agenda-items gains `concerns`, `local_concern`, `matches_local_concern` and concern ranking (+ 2 tests, 2 updated).
- Web: concern line and "Matches local concern" tag; `concernLabel` and `concernSummary` (+ tests); `api.types.ts` (additions only).
- Docs: `data-center-local-concerns.md`.

## CI Status
Checked on the head commit before merge; see the PR's Checks tab.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: none.
- Fabricated data: none. Every share is a count over recorded objections; no constant (including the 41% from the plan) is shown; empty areas say so.
- Personal data: none. Counts only, no names.
- Destructive changes: none; one additive column on `data_center_agenda_item`.

## Strengths
- One shared word list for both sides of the match, so "water" means the same thing in the area profile and on the item.
- The dominance bar (3 mentions) keeps one comment from reordering a feed.
- Ranking stays inside "upcoming" and "past", so concern never pushes a past meeting above an upcoming one.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Word matching will miss paraphrases ("the creek will dry up") and can catch incidental words ("trees" in a parks objection reads as land). The counts are shown, so the basis is visible. An LLM classifier could replace the lists later.
- The area is matched by `state_code` + `jurisdiction_name` text, as `event_decision` carries it. A name spelled differently between agendas and analyses won't join.
- "Cooling" counts as water. That's right for data centers, and rare in other objections.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first, Contract before first commit | ✅ #251 |
| Branch `<type>/<issue>-<slug>`, `Closes #251` | ✅ |
| Conventional Commits | ✅ |
| Transformations in dbt | ✅ |
| PK on public relation; FK where a relationship exists | ✅ PK `area_concern_id`; the area is a name pair, recorded |
| No fabricated data | ✅ |
| Scope label rule | ✅ concern line names the area it describes |
| Decisions written down | ✅ `data-center-local-concerns.md` |

## Test Coverage
- API: 6 new or updated tests (ordering puts concern between upcoming and date; fields served; concerns endpoint for city, national, empty, errors).
- dbt and SQL on PostgreSQL with stub decisions: shares, ranks, the 3-mention bar, blank objections dropped, national row; item tags; and the live ranking query, where a later water item outranks a sooner traffic item in a water-dominant city.
- Web: `concernLabel` / `concernSummary` tests; `tsc` and eslint clean.
- Not covered: real objections from the warehouse.

## Verdict
**approve-with-nits.**
