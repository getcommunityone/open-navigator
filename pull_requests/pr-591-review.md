---
pr: 591
branch: fix/504-topic-pill-counts
title: "fix(web_app): topic pill counts are meetings in the active scope, with a city note"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(web_app): topic pill counts are meetings in the active scope, with a city note

## Summary
The PR makes every Browse Topics pill and flyout row show the API's `meeting_count` ("193 meetings", "—" when
absent) instead of the national CivicSearch snippet count, so the number follows the state filter. It adds a note
under the pills when a city is carried in and the city scope is on ("Topic counts cover all of GA. Counts for
Atlanta alone aren't available yet."), so the "📍 Atlanta" label doesn't sit over state numbers. The change is
frontend-only and I could reproduce its claims: the API already returned a state-scoped `meeting_count` for every
topic, and the page was ignoring it. The data shown is real, the empty state is an em dash, and CI is green. The
one real problem is in the premise of the city half: the PR and #590 say no city-grain topic counts exist, but a
city-grain mart for them is already built in `gold` (unpublished). That doesn't block this PR, since the note is
honest about what the page shows, but #590 should be corrected before someone builds a duplicate.

## Scope of Change
- Files changed: 5 (+71 / -16, no generated files)
- Areas touched: web_app (page, util, type comment, test), tests (API)
- Commits:
  - `56759993` fix(web_app): topic pill counts are meetings in the active scope, with a city note
- Range reviewed: `0ba4fcd2..56759993` (`origin/main` merge base; the PR's base is `main`, not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | SUCCESS |
| Documentation Build (Docusaurus) | SUCCESS |
| Backend Tests (Python) | SUCCESS |
| API Types (OpenAPI -> TypeScript) | SUCCESS |
| PR conventions (linked issue) | SUCCESS |
| Detect Docker-relevant changes | SUCCESS |
| Docker Build Test (Full Stack) | SKIPPED (not required; no Docker files change) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The diff has no keys, tokens, URLs or `.env` content.
- **Fabricated data in a served path:** clean. The numbers 63046 and 193 appear only in a test fixture
  (`tests/test_api_topics.py`). The served code shows `meeting_count` from the API and "—" when it is null,
  undefined or NaN (`topicMeetingCountLabel`). Nothing is defaulted to a number.
- **Personal data:** clean. A city or state name from the URL is shown back in the note; nothing is stored or
  logged.
- **Destructive or bulky data changes:** clean. No data files, no warehouse writes, no deletions.

## Strengths
- Fixes the actual cause. Both the pill and the flyout row were reading the wrong field; they now read the
  scoped one, and the hover text names the scope ("in AL" / "nationally"). The hover no longer names a city that
  the count doesn't cover (previously `placeLabel` could be a city over a state number, for the curated pill).
- Honest about the grain it can't deliver. The note appears only when `scopedCity && stateCode`, so it goes away
  with the "All of XX" toggle, and the label and data stay in agreement (`CLAUDE.md`, scope label rule).
- Small, pure helper (`topicCounts.ts`) with a unit test, rather than inline strings.
- The PR body says plainly what was not done (city counts, ordering, `UnifiedSearch`) and that it wasn't checked
  in a browser.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **PR body and #590: "the only per-topic count tables are national and per state" is wrong; a city-grain topic
   count mart already exists.** `dbt_project/models/marts/browse_entity_place_transcript_count.sql` (PK
   `entity_type, entity_id, state_code, jurisdiction_name`, `count(distinct video_id)`, topics included) is
   built in the local warehouse as `gold.browse_entity_place_transcript_count`: 24,477 topic rows covering all 77
   topics (also 1,978 place, 22,614 cause, 457 question rows). *Verified read-only:* for the top topic in GA it
   returns Forsyth 110, Atlanta 73, Pickens County 33, Savannah 31, Columbus 13, against 366 for all of GA from
   the state mart the page uses now. It is not in `public` locally (`public.browse_entity_place_transcript_count`
   doesn't exist), and nothing in the repo outside its own model and schema file references it. So the data isn't
   missing; it's unpublished and unused. The note text ("aren't available yet") is still true of what the page
   serves, so this PR is fine to merge. But #590's contract ("a model in `public`, one row per (topic_id,
   state_code, jurisdiction_id)... size it first") would build a second mart for the same thing. *Fix:* add a
   dated line to #590 pointing at this mart, so the work becomes "publish it (storage check for Neon) and add the
   `city` parameter to `GET /api/topics`", and note that it is keyed by `jurisdiction_name`, not a jurisdiction
   id.

### 🔵 Nits / suggestions (Minor)
2. **`tests/test_api_topics.py`: the new API test pins existing behaviour, so it would pass without this PR.**
   The PR changes no API code. *Verified:* the test passes on the PR head (9 passed) and its assertions hold
   against the unchanged `_TOPICS_SQL`. It is a useful guard (it fails if someone adds a per-source branch to the
   count), but it isn't a regression test for the bug. The bug was in the page, and `BrowseTopics.tsx`'s use of
   the helper and the city note have no test. The helper tests (`topicCounts.test.ts`) would fail without the PR
   (the module is new). *Suggestion:* a small page test (or a component test) for "city carried in and city scope
   on → note shown; state only → no note".
3. **`BrowseTopics.tsx:103`: pill order is still by national snippet volume.** Under `?state=AL` the pills read
   193, 55, 63, 53, 42, 436, so the visible numbers are not in order, which looks odd next to a count. The PR
   discloses this and leaves it; it's a follow-up issue (`action-item`) if it isn't already one, since the API
   sorts by `transcript_occurrences`.
4. **Browser check outstanding.** The PR says it wasn't opened in a browser (vite config needs vitest), and I
   didn't either. The reviewer step in the PR body (open `?state=AL` and `?state=GA&city=Atlanta`) is still open.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/504-topic-pill-counts`; body `Refs #504` (part of a larger issue); #504 has Problem, Done when, Contract, Read first; the follow-up is its own issue (#590) |
| Conventional Commits | Yes | `fix(web_app): …` with co-author trailer |
| No fabricated data | Yes | Em dash when no count; no stand-in numbers |
| New Python in `packages/` | n/a | Only a test changed |
| dbt for transformations | n/a | No SQL or dbt change (see finding 1 for the existing mart) |
| Naming | n/a | |
| Keys | n/a | No model exposed |
| Calendar years | n/a | |
| Scope label matches filter | Yes | Hover and note name the scope the count covers; the city note shows only when the city scope is on. The decision list below is city-scoped and the counts are state-scoped, and the page says so |
| Match evidence on filtered tiles | n/a | Counts, not tiles |
| Docs | n/a | |
| Telemetry and logging | n/a | No API or script change |
| Tests | Partial | Helper tested; page wiring and the note untested; the API test is a characterization test (finding 2) |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage
- **Run locally (in the worktree, with the worktree's code on `PYTHONPATH`):**
  - `pytest tests/test_api_topics.py`: 9 passed (8 on `main`, plus the new test).
  - `npx tsc --noEmit -p web_app`: no errors outside `*.test.ts` (no unused-variable errors from the removed
    inline helpers).
  - `topicCounts.ts` run with Node's TypeScript stripping: `19,648 meetings`, `1 meeting`, `—` for null, and both
    titles match the test's expectations. (vitest isn't installed here; CI's `npm test` covers the file.)
  - `ruff check tests/test_api_topics.py`: clean.
  - **Read-only warehouse query:** the real `_TOPICS_SQL` against the local `public` schema: national 77 topics
    (first row 19,648); `AL` 76 topics (first row 193, none null); `ZZ` 0 topics. This matches the PR body. The
    PR's phrase "top: 193" means the first row by snippet order; the largest AL count is 1,180.
- **Not verified:** that `count(distinct video_id)` equals "meetings" for every transcript (one meeting with two
  videos would count twice). The label has been "meetings" for the curated pill since #503, so this PR doesn't
  change that. Not checked in a browser.

## Verdict
**approve-with-nits.** Nothing blocks the merge: the change is correct, shows only real values, and the note
keeps the label and data honest. Before or after merging, correct #590 (finding 1) so the city work reuses the
existing `browse_entity_place_transcript_count` mart instead of building a second one. The test and ordering
nits can follow as `action-item` issues.
