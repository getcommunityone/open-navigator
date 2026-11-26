---
title: Story charts - timeline, dumbbell and unit matrix
description: Design, data contract and thresholds for the story Meetings screen's trend line with a milestone track, the period dumbbell and the unit matrix (#1140).
---

# Story charts: timeline, dumbbell and unit matrix

**Issue:** [#1140](https://github.com/getcommunityone/open-navigator/issues/1140)
**Status:** built (2026-11-26)

The owner asked for the formats of three reference mockups (sections 01, 03 and 05 of the sample page) in place of the
story's per-year dot blocks. They are ported as React components fed only by the warehouse; none of the sample data is used.

| Reference | Component | Where |
| --- | --- | --- |
| 05 Scroll timeline | `web_app/src/components/stance/TimelineChart.tsx` | Meetings screen, top |
| 03 Dumbbell comparison | `web_app/src/components/stance/DumbbellChart.tsx` | Meetings screen, under the timeline (national and state scope) |
| 01 Unit matrix | `web_app/src/components/stance/UnitMatrixChart.tsx` | Meetings screen (passages), decisions, agendas, jobs claims |

All three are dispatched from `ChartPanel.tsx`, use the story's folio tokens (`--ink`, `--violet`, `--vermilion`,
`--rule` …, re-themed by the house theme) through `storyCharts.css`, and turn off their motion under
`prefers-reduced-motion`. Pure logic lives in `web_app/src/utils/storyTimeline.ts` and `web_app/src/utils/unitMatrix.ts`,
with vitest suites beside them.

## Data

### `recorded_meeting_year` (dbt mart, gold → public view)

The denominator for every share. One row per (state_code, jurisdiction_id, jurisdiction_name, meeting_year): distinct
meeting videos in `event_youtube_with_jurisdiction` that have a usable transcript (`stg_bronze_event_youtube_transcript`,
not excluded or tombstoned). Undated and future-dated meetings are left out. PK `recorded_meeting_year_id` (md5 of the
grain); FK `jurisdiction_id → jurisdictions`. `meeting_year` is an integer; the API sends it as a string. It is a table
because the count takes about three minutes over ~180k transcripts.

The topic counts come from transcripts of the same catalog (`data_center_meeting_mention` for data centers,
`topic_transcript_link` for other curated topics), so meetings / recorded meetings is a real share. A share is null
when a topic count is larger than its denominator (never capped to 100%).

### `GET /api/topics/{topic}/timeline?state=&city=`

`api/routes/topic_timeline.py`. `topic` is `civicsearch_topic.query_id` (`data-centers`, `water-fluoridation`, …).

- `years: [{year: "2026", meetings, passages, all_recorded_meetings, share}]` from the first year the topic came up to the
  last year on record. A year with neither topic meetings nor recorded meetings is absent. `passages` is null for topics
  other than data centers (their links are one row per meeting).
- `milestones: [{date, kind, place, state_code, title, url, video_id, source}]`, oldest first. `kind` is `approved`,
  `denied`, `tabled`, `moratorium` (from `data_center_meeting_lean.dc_outcome`, or `topic_meeting_lean.outcome_group`
  `advanced` / `blocked` / `tabled_or_deferred`, with `source: "ai_reading"`), or `bill_enacted` (from
  `topic_legislation_bill` with `status = 'enacted'`, `source: "record"`). Rows flagged `excluded_no_item` are skipped.
- `undated_meetings`, `total_meetings`, `total_passages`, `coverage_available`, `bills_available`. A missing relation
  (`recorded_meeting_year`, a lean table, `topic_legislation_bill`) is checked with `to_regclass` and skipped, not a 500.
  `topic_legislation_bill` is gold-only today, so `bills_available` is false on the public serving path.

### `GET /api/topics/{topic}/period-compare?state=&from=&to=`

Rows `[{key, label, earlier_share, later_share, earlier_meetings, later_meetings, earlier_recorded, later_recorded}]`, by
state (national) or by government name (state scope). Defaults: `to` = this year, `from` = last year.

**Thresholds** (returned with the rows as `min_recorded_meetings` and `min_topic_meetings`):

- at least **20 recorded meetings in each year** (`MIN_RECORDED_MEETINGS`), so one meeting can't swing a share from 0% to 100%;
- at least **3 topic meetings across the two years** (`MIN_TOPIC_MEETINGS`), so a row shows the topic, not noise.

Rows under them are counted in `hidden_rows` (places where the topic never came up are not counted) and the chart says
how many were left out. At state scope most towns record fewer than 20 meetings a year today (Texas: 18 towns with data
center meetings, none qualifies), so the chart says no town can be compared yet and points to the national view.

### Meeting passages carry their meeting's AI reading

`GET /api/data-centers/meeting-mentions` items gain `ai_outcome` and `ai_public_lean` from `data_center_meeting_lean`
(null when not screened or when the meeting had no data center item), for the unit matrix's outcome and public groupings.

## Trend line

- Series builder `buildSeries(years, mode)`: runs of consecutive years; a run breaks at a missing year or a gap year.
- A year with no topic meetings is drawn as a real 0 only when at least **25 recorded meetings** exist that year
  (`MIN_RECORDED_FOR_ZERO`); below that it is a gap (Texas 2024 has 7 recorded meetings). The note lists gap years.
- The line draws in once (`stroke-dashoffset` on a `pathLength=1` path); none with reduced motion.
- Toggle **Meetings / Share of recorded meetings**, shown only when shares exist.
- The coverage note is always shown: "Meetings in our record by year; recording coverage grew sharply in 2025–26, so the
  rise partly reflects coverage."

## Milestone track

One lane per kind present (never an empty lane), on the line's x scale (a year's point sits mid-year; a milestone sits
at its date). The selected marker is larger and vermilion; the default is the newest. Arrow keys, Home and End move the
selection, clamped at the ends (`stepMarker`). The card shows date, kind, place, the meeting or bill title, an
"AI reading" or "Official record" tag, and a link. Under 560px the track becomes a tap list, newest first, 12 at a time.

## Dumbbell

Hollow circle = earlier year, filled dot = later year, line violet for a rise and vermilion for a fall, ±pp at the right
(true minus sign). Sort by later, by change or by earlier (`sortDumbbell`); rows slide to their new rank. The first 12
rows are drawn, with "Show all". Each row is focusable with a full spoken label; **Show data table** lists every row.

## Unit matrix

One square per listed record, never per estimate. Groupings come from real fields on each record (`Dot.facets`):

| Toggle | Field | Records |
| --- | --- | --- |
| All | – | all |
| the chart's own (By phase, Upcoming or past, Debated or not) | the endpoint's grouping | jobs claims, agendas, decisions |
| By year | meeting / document date | all four charts |
| By state (national) / By town (state scope) | `state_code` / `jurisdiction_name` | passages, agendas, decisions |
| By outcome (AI reading) | passages: `ai_outcome`; decisions: recorded outcome text | passages, decisions |
| By who spoke (AI reading) | `ai_public_lean` | passages |

A grouping is offered only when at least one record carries its field. Records without it are counted in a group that
says so ("Date not given", "Not screened"), drawn as outlined squares, so groups always add up to the squares drawn. No
group is drawn for zero records. Places beyond the top 8 fold into "Other places (n)". Labels read "Name · N (x%)", the
percentage over the records drawn, and the note says whether those are all the records in scope or the most recent shown.
Square *i* is always record *i*, so a regrouping slides squares to new places (`transform` transition, staggered);
reduced motion jumps. Arrow keys walk squares in reading order; a meeting square plays its recording, others open their
source; **Show data table** lists the current groups.
