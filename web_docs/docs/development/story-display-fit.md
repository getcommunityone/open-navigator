---
title: Story display fits the data
description: One shared rule picks every story panel's display from its count (list, sentence, count bars, line, unit chart), so small records are not drawn as charts (#1289).
---

# Story display fits the data

**Issue:** [#1289](https://github.com/getcommunityone/open-navigator/issues/1289) · **Code:** `web_app/src/utils/displayFit.ts`
(`pickDisplay`), `web_app/src/components/stance/FitDisplay.tsx`

## Problem

Each story panel chose its own figure whatever the count. The Alabama Proposals panel drew 3 projects as 3 squares with a
legend, "Tap a dot to open it." and a FIG. caption; larger panels drew hundreds of squares with percentages. The owner
(27 Nov 2026) asked that displays fit the amount of data, with one shared rule and no per-panel choices.

## Decision: one rule, from the count alone

| Count | Display |
|---|---|
| 0 items | "No recorded &lt;items&gt; yet", with what was searched. No row of zeros. |
| 1–5 items | A sentence and a list of the items (name, status, place, date, link). No chart, dots or legend. |
| 2–7 categories, total under 20 | The numbers in a sentence. No percentages. The records stay one click away ("Show the 10 decisions"). |
| 2–7 categories, total 20 or more | Sorted horizontal bars labelled with counts. |
| 8 or more categories | The top 7 plus "Other". |
| Time series | A line only with 6 or more points; fewer read as "2025: 3; 2026: 14." |
| Dot or unit chart | Only for about 20–200 individual items in one category. |

The order of the checks is the table's: empty, then a series, then a list, then categories, then single-category units.
Thresholds live in `displayFit.ts` (`LIST_MAX`, `CATEGORY_MAX`, `BARS_MIN_TOTAL`, `LINE_MIN_POINTS`, `UNITS_MIN`, `UNITS_MAX`),
each with a test in `displayFit.test.ts`.

## Where it applies

- Every record panel drawn by `ChartPanel` (sites, projects, meetings, agendas, decisions, gatherings, jobs claims) and the
  concerns panel, which used to be a share dumbbell with percentages and is now count bars.
- The speaker dots under Who spoke up (`PositionsBlock`).
- The Meetings timeline (`TimelineChart`): the line needs 6 years with meetings.

Only the unit chart keeps its FIG. caption, legend and "tap a dot" hint. A list or a sentence is the data itself and carries a
one-line source; bars keep the data table toggle (counts only, no share column).

Not covered here: the Overview's period dumbbell and the maps, which compare places rather than count records.

## Speaker counts

A speaker figure reads **—** ("not available yet" to screen readers) when no meeting in scope was reviewed, and **0** only
when meetings were reviewed and nobody spoke. With nobody speaking, the line under the figures says "No public speakers in
the 24 meetings reviewed in Alabama." instead of "From 1 meeting …", which counted the meeting with the vote.
