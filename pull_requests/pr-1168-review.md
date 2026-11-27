---
pr: 1168
branch: feat/1140-timeline-dumbbell
title: "feat(stories): Meetings screen becomes a trend line with a milestone track, plus a period dumbbell and unit matrix, for every topic"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: general-purpose read-only subagent and coordinator
verdict: approve-with-nits
---

# PR Review: Meetings screen trend line, milestone track, period dumbbell and unit matrix (#1140)

## Summary
This PR adds `GET /api/topics/{topic}/timeline` and `/period-compare`, a `recorded_meeting_year` mart as the denominator for shares, and three React charts ported from the owner's reference (trend line with milestone track, period dumbbell, animated unit matrix). They are wired into the data-center story's Meetings screen and into every topic story. All numbers come from the warehouse. Missing years are gaps, and thresholds hide thin rows and say how many. The reviewer found no critical issues. Its Important findings were verified, and those in scope were fixed on the branch. The city-substring match is a site-wide convention and went to a follow-up (#1171). Verdict: approve with nits.

## Scope of Change
- Files changed: 23 (+2746 / -5, excluding `api.types.ts`)
- Areas touched: api, web_app, web_docs, dbt_project
- Commits: f1343436 feat (charts, API, mart); f4c3cd7d feat (topic stories); 1536046d style (ruff); 51fa7bda fix (topic_meeting_lean contract + review fixes); plus two merges of origin/main
- Range reviewed: `ff94e85f..51fa7bda` (then merged with main)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | see PR checks on the head commit |
| Documentation Build | see PR checks |
| Backend Tests | see PR checks |
| API Types | see PR checks |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. No defaulted numbers. `_topic`'s "Data centers" fallback is a name only. A year with no data is absent or drawn as a gap, and `share` is null when it can't be computed.
- Personal data: clean. No people data. Milestones are meetings (place, date, title).
- Destructive data changes: clean. A new dbt table only, built through dbt.

## Strengths
- The SQL builders are pure and unit-tested. Every relation that may be missing is checked with `to_regclass` and degrades without a 500.
- Shares are never capped: `_share` returns null when n > d, and period rows are hidden when topic > recorded.
- Reduced motion is honoured in both CSS and JS. Every chart has a data table, arrow-key navigation and a tap list on phones.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **FIXED** `api/routes/topic_timeline.py` milestones for curated topics read `topic_slug`, `outcome_group` and `excluded_no_item`. Those columns are not in the `topic_meeting_lean` model that just landed on main (#1166), so once dbt rebuilds, every topic timeline would have returned 503. It now reads `outcome` by `topic_id`, and a lean table of another shape drops the milestones but keeps the line (new pytest).
- **FIXED** At city scope, curated topics counted the numerator by `city OR jurisdiction_name` but the denominator by `jurisdiction_name`. Both now use `jurisdiction_name`.
- **FOLLOW-UP #1171** City scope uses a substring `ILIKE`, so "Tuscaloosa" also matches "Tuscaloosa County". This is the existing convention across `data_centers.py` and `topics.py`. The timeline keeps it so it agrees with the passages on the same screen, and the fix belongs site-wide.

### 🔵 Nits / suggestions (Minor)
- **FIXED** `UnitMatrixChart.tsx`: the roving index is clamped when the scope narrows, so one square always stays tabbable.
- **FIXED** `DumbbellChart.tsx`: the reveal waits for rows, so the animation plays.
- **FIXED** Period compare ignores future-dated curated-topic meetings.
- **Open** `storyCharts.css`: `.sc-line` is drawn fully for one frame before `is-drawing` animates it. The effect is cosmetic.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | `feat/1140-…`, `Closes #1140`; the issue has all four parts |
| Conventional Commits | yes | co-author trailers present |
| No fabricated data | yes | scan clean |
| New Python in `packages/` | n/a | API route only |
| dbt for transformations | yes | the denominator is a dbt mart |
| Naming | yes | `state_code` + `state`; no dim/fact |
| Keys | yes | PK `recorded_meeting_year_id`; FK `jurisdiction_id → jurisdictions`; both created in Postgres |
| Calendar years | yes | integer `meeting_year`; strings on the wire |
| Scope label matches filter | yes, with caveat | label follows `?state=&city=`; substring caveat in #1171 |
| Match evidence | n/a | no new content-filtered tiles |
| Docs | yes | `development/story-charts-timeline-dumbbell.md`, `guides/data-stories.md` |
| Telemetry | yes | OTel spans on both routes |
| Tests | yes | pytest for the endpoints; vitest for the series builder, marker step, dumbbell sort and matrix groups |

## Test Coverage
Run locally:
- pytest: 145 passed (topic timeline, topic and data-center routes)
- vitest: 62 files, 580 tests
- `tsc --noEmit` clean; web_app build and web_docs build OK
- ruff clean on the new files
- `dbt build --select recorded_meeting_year`: PASS=18; `dbt ls --select recorded_meeting_year+` shows nothing downstream

Checked against the local warehouse: TX gives 71 meetings and 278 passages, with 2026 at 38 of 509 recorded meetings. Desktop and phone screenshots were checked locally.

## Verdict
Approve with nits. Nothing is blocking. The substring city match is tracked in #1171.
