---
title: Story charts - timeline, dumbbell and unit matrix
description: Design, data contract and thresholds for the story Meetings screen's trend line with a milestone track, the period dumbbell and the unit matrix (#1140).
---

# Story charts: timeline, dumbbell and unit matrix

**Issue:** [#1140](https://github.com/getcommunityone/open-navigator/issues/1140)
**Status:** built (2026-11-26); thin-coverage years and the production milestone fix: [#1207](https://github.com/getcommunityone/open-navigator/issues/1207)

The owner asked for the formats of three reference mockups (sections 01, 03 and 05 of the sample page) in place of the
story's per-year dot blocks. They are ported as React components fed only by the warehouse; none of the sample data is used.

| Reference | Component | Where |
| --- | --- | --- |
| 05 Scroll timeline | `web_app/src/components/stance/TimelineChart.tsx` | Data-center story: Meetings screen, top. Every other topic story (`TopicStory.tsx`): "Meetings over time", under the map |
| 03 Dumbbell comparison | `web_app/src/components/stance/DumbbellChart.tsx` | Under the timeline, in both places (national and state scope) |
| 01 Unit matrix | `web_app/src/components/stance/UnitMatrixChart.tsx` | Meetings screen (passages), decisions, agendas, jobs claims |

On the data-center story all three are dispatched from `ChartPanel.tsx`; topic stories (`web_app/src/pages/TopicStory.tsx`) draw the timeline and dumbbell with the topic's slug inside a `.folio` block. All three use the story's folio tokens (`--ink`, `--violet`, `--vermilion`,
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
  `denied`, `tabled`, `moratorium` (from `data_center_meeting_lean.dc_outcome`, or `topic_meeting_lean.outcome`
  for the topic's `topic_id`, both `approved` / `denied` / `tabled_or_deferred` / `moratorium`, with
  `source: "ai_reading"`), or `bill_enacted` (from `topic_legislation_bill` with `status = 'enacted'`,
  `source: "record"`). `discussed_no_action`, `no_item` and `no_data_center_item` are never milestones. If the lean
  table's shape doesn't match, the line still draws and the milestones are left out.
- The milestone queries read only columns in the lean models' contracts (`_schema_data_center_meeting_lean.yml`,
  `_schema_topic_meeting_lean.yml`); `tests/test_api_topic_timeline.py` checks this. Until #1207 they also read
  `excluded_no_item`, a column only the local warehouse had (planned in #1136, never in the model). On the production
  serving copy the query failed, the route's fallback dropped the milestones, and the live track was empty at every
  scope (315 milestones nationally and 27 in Georgia locally, 0 in production). The same column broke the
  meeting-mentions `ai_outcome` / `ai_public_lean` stamps in production.
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
(null when not screened; `ai_outcome` is null when the reading was `no_data_center_item`), for the unit matrix's outcome
and public groupings.

## Trend line

- Series builder `buildSeries(years, mode)`: runs of consecutive years; a run breaks at a missing year or a gap year.
- A year with no topic meetings is drawn as a real 0 only when at least **25 recorded meetings** exist that year
  (`MIN_RECORDED_FOR_ZERO`); below that it is a gap (Texas 2024 has 7 recorded meetings). The note lists gap years.
- The line draws in once (`stroke-dashoffset` on a `pathLength=1` path); none with reduced motion.
- Toggle **Meetings / Share of recorded meetings**, shown only when shares exist.

### Thin recording coverage (#1207)

Recorded meetings per year are not steady. Nationally (2026-11-26): 12,476 (2018), 12,767, 15,122, 15,162, 12,525
(2022), 5,724 (2023), **932 (2024)**, 14,038 (2025), 16,873 (2026). 2024 is a hole in our recordings, so every topic's
count plunged that year (guns 1,022 → 603 → 50 → 598) while its share stayed normal (guns 5.4%). The 25-meeting floor
can't catch a year with 932 recordings.

**The rule** (`thinYears` in `storyTimeline.ts`): a year is **thin** when its recorded meetings are below **25%** of
both

1. the median of its neighbours' recorded meetings, up to **2 years on each side** (`THIN_WINDOW`), so the year is a dip
   and not a step on the ramp; and
2. the median of every recorded year in the scope, so a step on a steep ramp is not called a hole.

It must also be a **dip**: some year on each side recorded more, so the first year of a ramp and the latest year are
never thin. Years already flagged are left out of their neighbours' medians and the test repeats until nothing new is
flagged, so every year of a multi-year hole is caught, not only its two ends. It needs at least three recorded years.
Ratios, not counts, so it works at every scope:

| Scope | Result | Why |
| --- | --- | --- |
| National | 2024 only | 932 against a neighbour median of ~13,300 and a scope median of ~5,200. 2009–2011 (311–1,140) sit far below the scope median but in line with their neighbours, so the ramp isn't flagged. |
| Georgia (data centers) | none | 2024 had 115 against 794 in 2025 (the neighbour test alone would flag it), but 2023 had 92 and the state's median is ~190: a ramp, not a hole. |
| A town with ~10 a year | the year with 1 | Both medians are ~10. |

One test alone fails one of these cases: the scope median flags the whole early ramp; the neighbour median flags
Georgia 2024 but not the lower 2023.

**Drawing.** In Meetings (count) mode a thin year is a **hollow point** joined by **dashed segments** (`splitRun`,
`.sc-line--thin`, which fades in after the solid line has drawn), never a solid plunge, and the note names it: "Only 932 meetings were recorded in 2024, so that year's
count is not comparable." In Share mode the share is still meaningful, so the year is drawn normally; a point is hollow
there only when the share is over fewer than 25 recorded meetings (`MIN_RECORDED_FOR_ZERO`), and the note says so. A year
that is already a gap (no topic meetings and under 25 recorded) stays a gap.

**Default mode** (`defaultSeriesMode`). When coverage is available and a year on the count line is thin, and every such
year still has at least 25 recorded meetings, the chart **opens on the share** of recorded meetings, with the toggle still offered, and the note says why ("… not comparable. The
share of recorded meetings still compares, so the chart opens on it; Meetings shows the counts."). Otherwise it opens on
counts, which are easier to read when every year is comparable. A thin year with fewer than 25 recorded meetings keeps the
chart on counts: its share would be a spike of its own (1 of 2 meetings is 50%), so "the share still compares" would be
untrue. Opening on a count line with a dashed hole would show a
plunge first and explain it second; the share answers the question the reader is asking (did attention to the topic
change?) without the recording hole. The reader's choice of toggle is kept while they stay on the chart.
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
