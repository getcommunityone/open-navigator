---
pr: 1218
branch: feat/1209-concerns-dumbbell
title: "feat(stories): draw the Concerns screen as a dumbbell against the nation"
author: johncbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve
---

# PR Review: draw the Concerns screen as a dumbbell against the nation

## Summary
The Data Center Story's Concerns screen changes from a dot strip to a dumbbell, using the vizjb12 §03 port in the house colours.

- **State or city scope:** hollow dot is the national share of concern mentions, filled dot is the place's share, and the right column is the difference in points. Sort by **By [place]**, **By difference** or **Nationally**.
- **National scope:** one dot per concern. `area_concern.objection_count` is the area's total objections repeated on every row, not a per-concern count, so the planned mentions-against-objections comparison would be fabricated. The PR says this, and so does the chart.
- **Shared drawing:** `DumbbellRows` is extracted from `DumbbellChart`, so the places dumbbell and the concerns dumbbell share one drawing. `DumbbellChart`'s props are unchanged.

The reviewer found no Critical issues. I fixed one rounding/colour mismatch and the reveal-on-scope-change in 60a8f031. Verdict: approve.

## Scope of Change
- Files changed: 9 (web_app 7, web_docs 2), excluding this review
- Areas touched: web_app (stance components, utils, CSS), web_docs
- Commits:
  - 6f8a4e56 feat(stories): draw the Concerns screen as a dumbbell against the nation
  - fbb4d5b3 docs(pr-1218): auto-write rubric review [skip review] (bot; superseded by this file)
  - 60a8f031 fix(stories): colour a dumbbell difference by its printed sign, replay the reveal on a new scope
  - 61ed5e93 merge of the bot commit
- Range reviewed: `5be3e1d5..HEAD`

## CI Status
| Check | Status |
|---|---|
| PR conventions | pass |
| Documentation Build | pass |
| Frontend Build | see PR checks on head |
| Backend Tests | see PR checks on head |
| API Types | see PR checks on head |
| Docker Build Test | skipped (no Docker changes) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean.
  - Every share is `mention_count` divided by the scope's real total.
  - On the national screen, `national` is `null` rather than invented, because there is no per-concern objection count.
  - An empty scope shows "No concerns are on record", never national figures.
  - Hard-coded numbers are only the `MIN_PLACE_MENTIONS = 2` threshold (documented) and fixtures in tests.
- **Personal data:** clean (aggregate counts only).
- **Destructive data changes:** clean (no API, dbt or warehouse changes).

## Strengths
- The data limitation was checked against `area_concern.sql` before the chart was designed. The chart is honest about it rather than drawing a meaningless 100%-everywhere dumbbell.
- Hidden concerns stay in the denominator, so leaving a row out never inflates the others. The note names what is hidden.
- `DumbbellRows` is reused, not copied. Keyboard focus, spoken labels, reduced motion, the tooltip and the data table are kept.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **`DumbbellRows.tsx`: phone layout constants differ from the old `DumbbellChart`.**
  - Changed: stacked `plotL` 8 → 22, `plotR` w−12 → w−26, `deltaW` 64 → 72, a computed legend position, and a label halo.
  - These are deliberate. At iPhone width the first and last axis labels were clipped (".0%", "100.0"), and "+71.8 pp" needs the wider column.
  - Checked by screenshot at iPhone 13, and noted here and in the PR. No action needed.
- **The reveal stayed "revealed" across a change of scope.** Fixed in 60a8f031: `DumbbellRows` is now keyed by scope in both callers, and a comment states the mount contract.

### 🔵 Nits / suggestions (Minor)
- **A tiny negative difference that prints as "+0.0 pp" was coloured as a fall.** Fixed in 60a8f031: `negative` now comes from the printed sign.
- **Single-value rows used the "rise" colour for plain shares.** Fixed in 60a8f031 with a neutral `sc-delta-flat`.
- **A city scope with no state name would read as National.** Not reachable: the story only sets `city` together with a state (`StoryScope` docs). Left as is.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1209, four parts; branch `feat/1209-…`; `Closes #1209` |
| Conventional Commits | yes | co-author trailer on agent commits |
| No fabricated data | yes | see scans |
| New Python in `packages/` | n/a | no Python |
| dbt for transformations | n/a | no SQL |
| Scope label matches filter | yes | title, legend, note and data all use `chartScopeLabel('concerns', scope)`; the API query reads the same `?state=&city=` |
| Docs | yes | guides/data-stories.md and development/story-charts-timeline-dumbbell.md updated |
| Tests | yes | `concernDumbbell.test.ts` |
| Telemetry and logging | n/a | |

## Test Coverage
- **New tests:** `web_app/src/utils/concernDumbbell.test.ts` covers national vs place, the three sort orders, a negative difference, the hidden count and denominator, the fallback when there are no national rows, and empty data.
- **Run locally:**
  - `npx tsc --noEmit` clean.
  - `npx vitest run`: 67 files, 614 tests.
  - `npm run build` passes for both web_app and web_docs.
- **Playwright** on `?screen=concerns` at national, TX and GA, at 1440×900 and iPhone 13:
  - GA sort and data table work.
  - The row focus label is correct.
  - No page errors.

## Verdict
Approve. Merge once the required checks are green on the head commit.
