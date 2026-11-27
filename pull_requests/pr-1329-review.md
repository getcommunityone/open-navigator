---
pr: 1329
branch: feat/1290-fit-display-to-data
title: "feat(stories): votes read by which way they went, speaker sources reconciled, topic control in the title, screens fit a phone"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent and coordinator
verdict: approve-with-nits
---

# PR Review: votes read by which way they went, speaker sources reconciled, topic control in the title, screens fit a phone

## Summary
This PR follows up #1298 (#1289). It adds `data_center_decision.vote_side` so a recorded vote counts by which way it went, and the vote check leans only at two thirds. That brings the national title back to "America hates data centers." (7 of 12 decisions for, 5 against, which is mixed). It also adds `caption_comments`, so Alabama no longer says "no public speakers" next to 62 caption comments, and the Who spoke up figures show a dash instead of 0. It puts the topic control into every topic's conclusion wording, sends the topic story's positions bars through `pickDisplay`, and fits each story screen to a phone. A read-only reviewer found three Important issues, and all three are fixed and verified. The remaining nits are noted below. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 25 vs `origin/main` (about +920 / -60).
- Areas touched: api, web_app, web_docs, dbt_project (one mart column and its ODCS contract).
- Commits: the feature commit, plus fixes for the More room, the merge-left CSS brace, the svg height fit, the vote_side and one-mart reviewer fixes, the contract regeneration, and merges of main (after #1315, #1317, #1326, #1327, #1335, #1336).
- Range reviewed: `f4f1bec3..0fc43f0a`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | success on 92d5b69e; re-runs on this head |
| Documentation Build | success on 92d5b69e |
| Backend Tests | success on 92d5b69e (the first run failed on a stale ODCS contract; regenerated) |
| API Types | success on 92d5b69e |
| PR conventions | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every new number comes from `data_center_decision`, `data_center_comment` or the caption facts. A missing table or column gives null, never 0, and pytest covers this.
- Personal data: clean. Only comment counts are added, never comment text or names.
- Destructive data changes: none. `data_center_decision` gains a column through dbt and is rebuilt locally with `dbt build -s data_center_decision` (18/18). `dbt ls -s data_center_decision+` lists no downstream models. No Neon writes.

## Strengths
- The vote direction lives in dbt (a keyword CASE with an `accepted_values` test), not in the app.
- The caption-facts reads are defensive: `to_jsonb(d) ->> 'vote_side'` keeps an older serving copy answering.
- `storyHeadlineTopic.test.ts` checks every topic × side for one topic control, no bracket and no repeated topic.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important): all fixed in this PR
- **vote_side sign** (`data_center_decision.sql`). A lifted or rejected moratorium that passed read as against, and a failed motion to deny read as against. Fixed with a lift/end/rescind/repeal/reject branch and a headline-only deny branch. I rebuilt the mart: all 12 live tallies read as before.
- **Two marts for one count** (`topic_caption_facts.py`). `decisions` came from `data_center_meeting_position` and the sides from `data_center_decision`. With the sides present, every vote count now comes from `data_center_decision`, and pytest covers it.
- **"for/against" on summed votes** (`stanceEvidence.ts` `evidenceFacts`). It now says "for/against" by decision side, and "yes/no votes" for the fallback.

### 🔵 Nits / suggestions (Minor)
- `useScreenFit` is a heuristic. The latest `e2e/story-fit.check.mjs` run passes most screens at 360×740 and 412×915. These still run under the bar at 360×740:
  - Alabama Decisions, now taller with #1327's supporter lines;
  - Texas Jobs (a payroll panel with two blocks) and Agendas;
  - the newer Upcoming and Bills screens from #1310 and #1335;
  - the guns timeline, by about 55px.
  Follow-up: a per-panel compact layout, rather than a generic zoom.
- `TopicPositionsBreakdown` now shows an explicit empty line when nothing is read (reviewer nit, fixed).
- `dropNextQuestion` would cut a question that contains a period ("St. Louis?"). No context line has one today.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #1290 has four parts plus a dated narrowing note after #1298 |
| Conventional Commits | ✅ | co-author trailer on each |
| No fabricated data | ✅ | nulls, not zeros |
| dbt for transformations | ✅ | vote_side in dbt |
| Keys | ✅ | grain and PK unchanged |
| Scope label matches filter | ✅ | caption facts and the drill echo the scope; the queries key on it |
| Docs | ✅ | new `development/story-vote-direction-and-phone-fit.md`; `story-captions.md` and `guides/data-stories.md` updated |
| Tests | ✅ | vitest 886/886, pytest caption facts 25/25, datamodels 38/38, tsc clean |

## Test Coverage
- vitest covers: the Alabama facts with caption comments; "no public speakers" only when there are none; a moratorium yes that isn't support; a headline that disagrees with votes read by side failing; every topic title; and dash versus 0.
- pytest covers: vote sides, one-mart counts, caption comments, scoping and missing tables.
- Playwright `e2e/story-fit.check.mjs` ran locally against my Vite (5367) and API (8061). Results are under Nits.

## Verdict
**approve-with-nits.** Nothing blocking. The phone-fit gaps listed above are follow-up work.
