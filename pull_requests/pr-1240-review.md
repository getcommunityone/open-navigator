---
pr: 1240
issue: 1230
branch: fix/1230-map-quotes-stance-meetings
title: "fix(stories): map cards quote real meetings where the public took a side"
reviewed_at: 2026-11-27
reviewer: claude (pr-review, with a read-only reviewer subagent)
verdict: approve
---

# PR Review: fix(stories): map cards quote real meetings where the public took a side

## Summary

The story map cards quoted each state's newest keyword passage. That is how Alabama's guns card ended up quoting an
interview. The PR picks the quote server-side instead. It skips recordings that Jev's existing `meeting_kind` reads as
not a meeting (the new `meeting_video_kind` mart), prefers meetings where the public took a side, newest first, and adds
a short stance line to the card. The selection SQL was run against TEMP fixture tables on Postgres, and against the real
warehouse before it went down. The review found two should-fix items. Both are fixed in 291e1514. Nothing blocking
remains.

## Scope of Change

- API: `api/routes/topics.py` changes the `/states` `newest` pick and adds `public_stance` with a fallback.
  `api/routes/data_centers.py` adds `quotes_per_state` with a fallback.
- dbt: adds `stg_jev__video_meeting_kind` and the `meeting_video_kind` mart (PK `video_id`, contract enforced). The
  mart is added to `publish_public_serving` and its launch scope, and the ODCS contract is regenerated.
- Web: `QuoteCard` gets a `stanceNote` prop and `StateQuote.stanceNote`. Also touched: `utils/topicPositions.ts`
  (`quoteStanceNote`, `dataCenterQuoteNote`), the topic and home cards, and the Data Center Story national map in
  `StoryScreenView`.
- Docs: `web_docs/docs/guides/data-stories.md`, the section "Which meeting a map card quotes (#1230)".

## CI Status

| Check | State |
|---|---|
| PR conventions | pass |
| Frontend Build, Documentation Build, API Types | pass on 74857c9e |
| Backend Tests | merge waits for green on the head commit |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- No secrets.
- No fabricated data. Every quote is a stored verbatim excerpt. The stance line only restates a classifier reading that
  exists. A meeting with no reading claims nothing beyond "Mentions <topic>" (fixed in review).
- No personal data. Nothing is tied to a person.
- No destructive data changes. One new table and a view.

## Strengths

- No new classifier. It reuses Jev's `meeting_kind`. The signals were measured and recorded in the issue: channel
  classification catches 0, `event_meeting` covers 1,205 of 18,045, and title patterns hit real meetings.
- Both endpoints fall back to the old newest pick on `UndefinedTable` / `UndefinedColumn`. Neither runs in an explicit
  transaction, so the retry is safe.
- The joins use the full keys (`topic_meeting_lean` on `(video_id, topic_id)`, `data_center_meeting_lean` on
  `video_id`), so there is no fan-out.
- The topic's position words come from `topicPositions.ts`, so the upcoming "Gun control" relabel carries through
  without code changes.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. `stg_jev__video_meeting_kind.sql`: the missing-bronze placeholder arm had no column aliases. If it became the first
   UNION arm, the outer `distinct on (video_id)` would fail. **Fixed** in 291e1514 (aliased).
2. `quoteStanceNote`: a meeting with no reading (`null`) was labelled "no public stance in this meeting", a claim with
   no record behind it. **Fixed**: `null` now gives only "Mentions <topic>", and `silent` keeps the no-stance line.
   Tests and docs are updated.

### 🔵 Nits / suggestions (Minor)
3. The speaker quotes on the home data-center map (`/positions?per_state=3`) don't go through `meeting_video_kind`. This
   is out of the issue's scope and filed as #1246.
4. The staging model had no yml entry. **Fixed**: it is documented, with `video_id` tested not_null and unique.

## Repo-Rule Compliance

| Rule | Status | Note |
|---|---|---|
| Issue first, four parts | ✅ | #1230 |
| Branch / PR naming, `Closes #` | ✅ | |
| Conventional Commits + attribution | ✅ | |
| Docs in the same PR | ✅ | data-stories.md |
| dbt PK/FK on public models | ✅ | PK `video_id`. No FK possible: no single-column parent; the reason is documented |
| Transformations in dbt | ✅ | The meeting-kind pick is in dbt. The API only joins and ranks |
| No Fabricated Data | ✅ | After fix 2 |
| Match evidence shown | ✅ | Verbatim `<mark>` excerpts kept |
| Privacy | ✅ | No person data |
| Follow-ups as issues | ✅ | #1241, #1242, #1246 |

## Test Coverage

- `tests/test_api_story_map_quotes.py` has route tests (mocked pool) and `live` SQL tests that run the real queries on
  TEMP fixtures. They cover: interview excluded, a stance meeting beats a newer keyword-only one, screened beats
  unscreened, split and silent mapping, one passage per meeting, and the fallbacks. All passed locally with
  `RUN_LIVE_TESTS=1`.
- Existing topic and data-center route suites: 65 passed. vitest: 696 passed. tsc, the web build and the docs build
  pass. `models.odcs --check` passes.
- Gap: a live browser check at Pixel 7 and 1440x900 couldn't run because the warehouse, API and Vite were down after
  the machine restart.

## Verdict

**approve**. The two should-fix items are fixed on the branch. Merge once required CI is green on the head commit.
