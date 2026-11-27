---
pr: 1280
branch: feat/1274-topic-legislation-map
title: "feat(stories): state legislation map, local-actions tracker and meeting positions for a topic"
author: agent (Claude Code)
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent and coordinator
verdict: approve-with-nits
---

# PR Review: state legislation map, local-actions tracker and meeting positions for a topic

## Summary
Adds a "Where policy is moving" section to every topic story: a state legislation map built from our OpenStates
bills (new dbt marts `topic_legislation_bill` / `topic_legislation_category`), a breakdown of the positions the public
took in meetings, and a tracker of what local bodies voted, both from `topic_meeting_lean`. The first review pass found
three important issues (live bills marked failed, presiding-officer signatures counted as enactment, an unbounded
national bill download); all three are fixed in 98ee887b and verified on the rebuilt mart. What remains is minor and
latent. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 32 (excluding the two generated ODCS contracts)
- Areas touched: api / web_app / web_docs / dbt_project / tests
- Commits:
  - 397e23ed feat(stories): state legislation map, local-actions tracker and meeting positions for a topic
  - 98ee887b fix(stories): legislation map loads counts, then one state's bills; stricter bill status rules
- Range reviewed: `origin/main..feat/1274-topic-legislation-map`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every figure comes from the API; loading, error and empty states are explicit; `pct()`
  returns null for a zero total; no fallback constants. Test fixtures stay in `tests/` and `*.test.ts`.
- Personal data / privacy: clean. Meetings are shown as a body's action (council, board), never a person's; positions
  are meeting counts, never speakers. Bills are public records.
- Destructive data changes: none. New dbt models and seeds only; no deletions.

## Strengths
- Topic-generic end to end: seeds drive keywords, scope and categories; any curated topic gets a map with no code.
- Keys enforced in Postgres: PK (topic_id, bill_id) and FKs to `civicsearch_topic`, `bills`, and the composite FK to
  `topic_legislation_category` (verified on `gold`).
- A bill whose text doesn't say which way is kept as "direction not stated" and shown by status only, not guessed.
- Fixes a real break: `topic_timeline` read `latest_action_date`, which the mart doesn't have.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Fixed in 98ee887b, each verified by rebuilding `topic_legislation_bill`:
- `topic_legislation_bill.sql` failed rule: bare `withdrawn` / `failed` / `on table` marked NC "Withdrawn From Com/Cal"
  (a procedural move) and failed amendments as failure. Now only sponsor withdrawals, failed passage votes and laid on
  the table count. Verified: NC 2025 session rows with that action are now pending (7) or passed_chamber (4); older ones
  are failed because their session is closed.
- Same file, enacted rule: `\msigned` counted "Signed by the Speaker / President of the Senate". Now a governor's
  signature (or NM's bare "Signed"), chaptered, act no., filed with the secretary of state. Verified: 0 enacted rows rest
  on a presiding officer's signature.
- `topic_policy.py` / `LegislationMap.tsx`: the map downloaded every bill nationally (guns ≈ 7.6 MB). Now
  `/legislation` returns counts per state × category × year × status (guns ≈ 200 KB), and a state's bills load from
  `/legislation/{state}` with the active filters, at most 200, with the match count shown.

### 🔵 Nits / suggestions (Minor)
- Fixed: the scoped state's panel couldn't be closed (`LegislationMap.tsx`); period buttons were `role="radio"`
  without arrow keys (now buttons with `aria-pressed`); local actions didn't filter `excluded_no_item` and always said
  available; Hawaii "GM" nominations were counted as bills.
- Open (latent): `int_bills__session_span.sql` first `is_closed` branch doesn't skip special sessions, and its special
  regex misses spellings like `2026F` / `20251E`. Replicated on current data: every closure since 2025 is correct.
- Open: no dbt test pins the status/category rules to known bills (e.g. UT HB 81 enacted, NC withdrawn-from-committee
  pending). Worth adding as singular tests.
- Scope label: positions and local actions follow `?state=`; the map is national by design with the scoped state
  outlined and opened, and its subtitle says "<state> highlighted".

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/1274-…`, `Closes #1274`, issue has all four parts; contract change dated on the issue; follow-ups #1275, #1278, #1279 |
| Conventional Commits | ✅ | both commits, co-author trailer |
| No fabricated data | ✅ | scan clean |
| New Python in `packages/` | ✅ | no new scripts; API route only |
| dbt for transformations | ✅ | matching, categories and status in dbt; the API only groups and filters served rows |
| Naming | ✅ | `state_code` + `state`; no dim_/fact_ |
| Keys | ✅ | PK + FKs declared and enforced |
| Calendar years | ✅ | integer in the mart; string on the wire |
| Scope label matches filter | ✅ | see nit |
| Match evidence on filtered tiles | n/a | no content-filtered tiles |
| Docs | ✅ | `guides/data-stories.md`, `development/topic-legislation-map.md` |
| Telemetry and logging | ✅ | OpenTelemetry spans per endpoint, loguru |
| Tests | ✅ | API tests for all four endpoints; util tests; timeline regression assertion |
| Shared libraries | n/a | no `packages/` change |

## Test Coverage
- `pytest tests/test_api_topic_policy.py tests/test_api_topic_timeline.py packages/datamodels/tests`: pass (24 + datamodels).
- `ruff check` on changed Python: clean. `python -m models.odcs --check`: current.
- `web_app`: `tsc --noEmit` clean, `vitest run` 724 passed, `npm run build` ok. Docusaurus build ok.
- `dbt ls --select <new models>+` lists only the new models and tests; `dbt build` of only the new nodes: PASS.
- Browser screenshots at 1440x900 and Pixel 7, national and `?state=NC`, checked by eye.

## Verdict
approve-with-nits. Merge once the required CI checks are green on the head commit.
