---
pr: 1219
branch: fix/1207-timeline-thin-coverage
title: "fix(stories): thinly recorded years draw hollow and dashed, the chart opens on the share, and milestones return in production"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent (general-purpose) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): thinly recorded years draw hollow and dashed, the chart opens on the share, and milestones return in production

## Summary
The PR adds a pure thin-coverage rule to the story timeline. A year is thin when its recorded meetings are below 25% of both its neighbours' median and the scope median, and it must be a dip. In count mode a thin year is drawn as a hollow point on dashed segments, and the note names it. When a drawn year is thin, the chart opens on the share of recorded meetings. The PR also fixes the empty milestone track in production: the milestone and mention-lean SQL read `excluded_no_item`, a column that is not in the `data_center_meeting_lean` model contract. A regression test now checks the SQL against `schema.yml`. It works locally (Playwright, before and after), and every check run locally passes. The reviewer found three minor issues, and all three are fixed in fd2092b5. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 9 (+315 / -19, excluding this review file)
- Areas touched: api, web_app, web_docs
- Commits:
  - bca64665 fix(stories): thinly recorded years draw hollow and dashed, the chart opens on the share, and milestones return in production (#1207)
  - cca4defd docs(pr-1219): auto-write rubric review [skip review]
  - fd2092b5 fix(stories): catch every year of a long recording hole, stay on counts when a thin share rests on too few meetings, fade the dashed piece in (#1207)
  - merge commits from origin/main and the bot review
- Range reviewed: `5be3e1d5..HEAD` (merge base with main)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | was pending when this was written (run locally: `npm run build` ok) |
| Documentation Build | was pending (run locally: ok; only the repo's existing broken-link warnings) |
| Backend Tests | was pending (run locally: 30 passed in the two touched route suites) |
| API Types | was pending (no response model change) |
| PR conventions | was pending (branch `fix/1207-…`, `Closes #1207`, the issue has all four parts) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every number in the new note comes from `all_recorded_meetings`. The test fixtures are real API values dated 2026-11-26 and are used only in tests.
- Personal data: clean.
- Destructive or bulky data changes: clean. No dbt or warehouse changes; the production cause was checked through public API responses only.

## Strengths
- The rule is pure, uses ratios, and has tests at national, state and town scale. The docs justify it with a table of real cases, including why neither test works alone.
- The root cause of the empty production track was found and is guarded by a contract test that would have failed before the fix.
- The UI change keeps the toggle, names the gap honestly, and never drops data.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
All three are fixed in fd2092b5.
1. **A hole of four or more years was flagged only at its ends.** `web_app/src/utils/storyTimeline.ts` `thinYears`.
   - Reviewer reproduced it with recorded counts `[1000,1000,100,100,100,100,1000,1000]`.
   - Fix: flagged years are left out of their neighbours' medians, and the test repeats until nothing new is flagged.
   - It now also requires a dip (some year on each side recorded more), so the start of the national ramp (2008) can't cascade into thin.
   - New vitest case added. The national data still flags exactly `[2024]`.
2. **Opening on Share could show a spike while the note says the share "still compares"** (for example a thin year with 1 of 2 meetings recorded). `defaultSeriesMode`.
   - Fix: the chart opens on Share only when every drawn thin year has at least `MIN_RECORDED_FOR_ZERO` recorded meetings.
   - New vitest case added.
3. **The dashed piece appeared before the solid line had drawn in.** `storyCharts.css`.
   - Fix: `.sc-line--thin` fades in after `--d-4`. No animation under reduced motion.

Noted, not changed: the reader's toggle choice carries across a scope change, because TimelineChart isn't keyed by scope. The docs describe that behaviour.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1207 has all four parts. Follow-up #1214 (topic outcome labels) is filed as an action-item. |
| Conventional Commits | Yes | Co-author trailer on agent commits |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | N/A | No new Python modules |
| dbt for transformations | Yes | No SQL logic moved into Python |
| Naming | N/A | |
| Keys | N/A | No model changes |
| Calendar years | Yes | Years stay strings on the wire and are parsed in the client |
| Scope label matches filter | Yes | The scope label is unchanged and the note names the scope's own counts |
| Match evidence on filtered tiles | N/A | |
| Docs | Yes | `story-charts-timeline-dumbbell.md` and `guides/data-stories.md` updated in this PR |
| Telemetry and logging | Yes | Existing spans unchanged |
| Tests | Yes | The thin rule, default mode, splitRun, isHollow and thinNote each have vitest cases. The SQL-vs-contract regression test fails on the old SQL. |
| Shared libraries | N/A | No `packages/` change |

## Test Coverage
Run locally on the final head:
- `pytest tests/test_api_topic_timeline.py tests/test_api_data_center_meeting_mentions.py`: 30 passed
- `ruff check` on the changed Python files: clean
- `tsc --noEmit`: clean
- `npx vitest run`: 66 files, 622 tests passed
- `npm run build`: ok. Docs build: ok

Playwright at 1440x900 and iPhone 13, on `/stories/guns` and `/stories/data-centers` (Overview and Meetings screens), national and `?state=GA`:
- National opens on the share with the 2024 note.
- In count mode 2024 is hollow and dashed.
- GA opens on counts.
- The DC track keeps 315 milestones nationally and 27 for GA.

Not covered by a test: the visual rendering (screenshots only), and production after deploy. The production fix is inferred from the live API's empty milestones together with the null `ai_outcome`, because there was no direct read access to the production database.

## Verdict
approve-with-nits. All nits are addressed. Merge once the required CI checks are green.
