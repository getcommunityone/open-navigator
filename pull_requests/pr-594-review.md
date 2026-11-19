---
pr: 594
branch: fix/484-meeting-state-labels
title: "fix(youtube): file the Detroit MI, Douglas County CO and Stillwater OK channels under their own governments"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(youtube): file the Detroit MI, Douglas County CO and Stillwater OK channels under their own governments

## Summary
The PR adds three channel-wide rows to the `youtube_channel_attribution_override` seed (Detroit MI, Douglas County CO,
Stillwater OK) and a singular dbt test, `assert_youtube_attribution_override_applied`. The seed rows are correct. The
channel ids, the jurisdiction ids, the states and every quoted title were checked against the local warehouse, and the
channels hold 121 / 88 / 122 videos as the body says. The PR is honest that it is only half of #484: nothing is
rebuilt or repaired yet, and the loader that stamps the wrong state is not fixed, so `Refs #484` is the right link.
The weak part is the new test. As written it cannot fail for the reason its comment and the PR body give (a re-crawl
bringing the old label back), and it is green today while the new rows are not yet applied. The data change is fine
to merge. The test should be reworked or its claim narrowed. Approve with nits.

## Scope of Change
- Files changed: 2 (+20 / -0, no generated files)
- Areas touched: dbt_project (seed, test)
- Commits:
  - `38166ebe` fix(youtube): file the Detroit MI, Douglas County CO and Stillwater OK channels under their own governments (carries the `Co-authored-by: Cursor` trailer)
- Range reviewed: `0ba4fcd2..38166ebe` (merge base of `origin/main` and `origin/fix/484-meeting-state-labels`; the PR base is `main`, not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required, no Docker files changed) |

All on head `38166ebe`. None of the required checks runs dbt, so CI says nothing about the seed or the new test.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The diff holds public YouTube channel ids, jurisdiction ids and public video titles. No keys, tokens, URLs with credentials or cookies.
- **Fabricated data in a served path:** clean. No numbers are invented. Each seed row's evidence quotes real titles, and all nine quoted titles exist verbatim in `bronze.bronze_event_youtube` on the claimed channel (checked by exact match). The mismatch counts in the PR body are not in the diff (see the nit on counts).
- **Personal data:** clean. Public government channels and public meeting titles only.
- **Destructive or bulky data changes:** clean. A 3-line seed edit and a read-only test. Nothing deletes `data/cache/`, no large files, and no warehouse table is written outside dbt. The `repair_youtube_channel_attribution` run-operation, which does write, is deliberately not run.

## Strengths
- The attribution is right and evidenced. Each row names the channel, the correct government and the verbatim titles that prove it. Titles such as "Mayor Mary Sheffield Charter Mandated Meeting" (Detroit MI), "Board of Douglas County Commissioners" with "Crystal Valley Interchange" (Douglas County CO), and "Stillwater Planning Commission 11/17/2026" (Stillwater OK) cannot belong to the Alabama places they were filed under.
- The jurisdiction ids resolve in `intermediate.int_jurisdictions` with the right pair of columns: `detroit_2622000` Detroit MI / Michigan, `douglas_08035` Douglas County CO / Colorado (county), `stillwater_4070300` Stillwater OK / Oklahoma. The seed's `relationships` test covers the id, and `state_code` carries both code and name through the intermediate model.
- The body is candid. It lists what was not run (the rebuild, the repair, `event_meeting` still unseen with MI/CO/OK) and what stays open on #526 (the loader). It does not claim to close #484, and it files the "Tuscaloosa, Alabama" text defect separately as #593.
- Channel-wide rows rather than per-video rows. The channels are single-government channels, so the fix covers future videos too.
- Seed hygiene: the CSV has 23 rows of 6 fields each (parsed with the `csv` module), embedded quotes are escaped correctly, and `issue` is 484 on all three rows.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`dbt_project/tests/assert_youtube_attribution_override_applied.sql:9-17`: the test cannot catch the regression it names, and passes today with the new rows unapplied.**
   - What the test does: it joins `int_youtube__attribution_override` (`o`) to `event_youtube_with_jurisdiction` (`y`) on `video_id` and returns rows where `y` differs from `o`. But `y` is a view, and its `a.video_id is not null then a.jurisdiction_id ...` branch reads that same `o` table (`models/marts/event_youtube_with_jurisdiction.sql`). For every video on an overridden channel the two sides are the same values by construction. The test can only fail if someone edits that `case` expression.
   - It does not cover a re-crawl. A re-crawl writes the old attribution into `bronze` and `civic_event`. The view overrides `bronze` anyway, so the test stays green. What a re-crawl does damage is `civic_event` and from there the append-only `event_meeting` / `event_decision` marts, which are where #484's labels are served. The test reads neither (`event_meeting` takes its state from `civic_event`, `models/marts/event_meeting.sql:52-63`).
   - It does not fail for the missing rebuild either. Verified read-only on the local warehouse: the three new seed rows are loaded, `int_youtube__attribution_override` has 0 rows for those channels (not yet rebuilt), and the compiled test returns 0 rows. In the same warehouse, `gold.event_meeting` has 22 (Detroit), 8 (Douglas) and 79 (Stillwater) meetings on those channels, all `state_code = 'AL'`. So the test is green while the exact symptom in #484 is live, and reverting the seed rows would not turn it red either (the intermediate model is derived from the seed).
   - Fix: compare the override with what is served downstream, for example `event_meeting` (joined on `video_id`) and `event_decision` through it, and `state_code` / `jurisdiction_name` against `o`, or against `civic_event` by `dedupe_key = 'youtube|' || video_id`. That test is red today and turns green after the repair, which is what the PR body wants it to show. Otherwise reword the comment and the PR body to say it only guards the view's `case` logic.
   - Impact: no wrong data is served because of it. The harm is false assurance, and #484's "with a test" is not met by it.

### 🔵 Nits / suggestions (Minor)
1. **PR body, "Those channels hold 15, 8 and 38 analysed meetings in `event_meeting`".** Not reproducible as stated. On the local warehouse the three channels have 22, 8 and 79 `event_meeting` rows (one per video, all AL). 15 / 8 / 38 matches the subset whose own `jurisdiction` text names the right place (for example 14 "City of Detroit, Michigan" + 1 "Detroit, Michigan"). The rest read "City of Tuscaloosa, Alabama" (the #593 defect, 1 / 1 / 34), a bare id, or "Detroit". The repair will relabel all 22 / 8 / 79 (it works per video on the channel), so the body understates what it will touch. Say which subset the numbers are.
2. **Seed `evidence` strings** (`youtube_channel_attribution_override.csv:21-23`) mix verbatim titles with prose and a phrase like "the meeting record names 'Stillwater, Oklahoma'". The existing rows use a `title:` prefix per quote. Not blocking: the schema asks for "the verbatim title(s), handle or website", and these meet it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/484-meeting-state-labels`. Body says `Refs #484`, correct for one part of a larger issue. #484 has Problem, Done when, Contract and Read first. The follow-up found is its own issue (#593); #526 is linked for the loader. PR conventions check passes |
| Conventional Commits | Yes | `fix(youtube): ...` with the Cursor co-author trailer |
| No fabricated data | Yes | Evidence titles verified verbatim; nothing invented |
| New Python in `packages/` | n/a | No Python |
| dbt for transformations | Yes | Seed plus a dbt test; no SQL logic in Python |
| Naming | Yes | `state_code` in the seed; `state` comes through `int_jurisdictions`; no `dim_` / `fact_` names |
| Keys | n/a | No new model in `public`; the seed keeps its `relationships` test to `int_jurisdictions` |
| Calendar years | n/a | No year columns |
| Scope label matches filter | n/a | No UI change. Effect after the repair: the AL label over MI/CO/OK meetings goes away |
| Match evidence on filtered tiles | n/a | No UI or API change |
| Docs | n/a | No docs added. The seed's description in `seeds/schema.yml` already documents the apply steps |
| Telemetry and logging | n/a | No FastAPI or script code |
| Tests | Partly | A test is added, but it would not have failed before the change or after a re-crawl (finding 1) |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage
- Run locally, all read-only (the warehouse at `localhost:5433` was reachable; `NEON_DATABASE_URL_DEV` is not set in this environment, so the local warehouse was used):
  - `dbt ls --select assert_youtube_attribution_override_applied youtube_channel_attribution_override int_youtube__attribution_override+` works from the worktree; the seed, the intermediate model, `event_youtube_with_jurisdiction` and their downstream marts resolve. The new test is in the DAG.
  - `dbt compile` of the new test is clean. Its compiled SQL, run read-only, returns 0 rows now (finding 1).
  - Seed and bronze checks: the three channels hold 121 / 88 / 122 videos, all nine quoted titles exist verbatim on the right channel, the three target ids exist with the expected states, and `B9RihIf7v5k` (the Stillwater plat video from #484) is on `UCqVPe2edQeGrfg4vmrFPa2Q`, as the body says.
- Not run, by instruction: `dbt seed|run|test|build`. The body's "seed and 4 schema tests pass" and "compiled and ran read-only, 121 / 88 / 122" are unverified as run commands. The inputs behind them reproduce: the rows are loaded in the warehouse, the bronze video counts match, and the jurisdiction ids resolve.
- Not covered: nothing tests that `event_meeting` / `event_decision` / `civic_event` carry the reviewed state. The loader stamping is untouched, and the PR says so.
- Python, ruff and `tsc` are not applicable (no Python or frontend files in the range).

## Verdict
**approve-with-nits.** The seed rows are correct, well evidenced, and safe to merge as a data fix. It does not close #484, and the PR body says so. Before the repair is run, either point the new test at the downstream marts (`event_meeting` and `event_decision`, or `civic_event`) so it is red now and green after the repair, or narrow its comment and the PR body to what it checks. Nit 1 is a body wording fix. After merge, run the three commands in the seed's description, then the repair dry run, and re-read the 22 / 8 / 79 counts.
