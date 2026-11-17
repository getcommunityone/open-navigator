---
sidebar_position: 33
title: What's New recent meetings
description: How the homepage What's New rail includes recent meetings that are transcribed but not analyzed yet, and the choices behind it.
---

# What's New recent meetings

The homepage "What's New" rail listed only AI-analyzed meetings (`public.meeting_browse`). Analysis stopped in early
June 2026, so the rail froze there while hundreds of newer meetings were transcribed. Since
[#509](https://github.com/getcommunityone/open-navigator/issues/509) the rail also shows those meetings, labelled
**Not yet analyzed**.

## How it works

- **dbt model** `recent_transcribed_meeting` (gold, published to `public`): one row per `video_id`, for a meeting
  with a transcript in `event_documents`, no row in `event_meeting`, a date in the last 180 days and not later than
  today. Primary key `video_id`; `jurisdiction_id` is a foreign key to `jurisdictions` (null when it doesn't resolve).
- **API**: `GET /api/meetings?sort=recent` with no topic, theme or question filter returns analyzed meetings and these
  rows together, newest first, under the same `state` / `city` / `q` scope. Unanalyzed items have `analyzed: false`,
  `meeting_id: null`, no counts, their `video_url`, and when they matched a curated topic or question, `evidence`,
  `evidence_label` and `jump_url`. A video that `meeting_browse` already serves is never repeated, so a meeting
  switches to its analyzed card as soon as it is analyzed. Dates later than today are left out on both legs.
- **Card**: a "Not yet analyzed" pill, title, date, place and the recording link. No decision or topic counts.

## Decisions

- **Evidence is copied, never cut at request time.** The passage comes from `topic_transcript_link.evidence_passage`
  (first) or `question_transcript_link.evidence`, both cut in dbt with `<mark>` around the matched words. Production
  Neon has no transcript text ([#496](https://github.com/getcommunityone/open-navigator/issues/496)), so nothing reads
  `event_documents.content` in the API.
- **Non-meetings are filtered twice.** The junk-channel gate (`event_youtube_with_jurisdiction`) drops channels that
  aren't governments. Government channels also post promos and ceremonies, so the title must also name a public
  meeting (`meeting_title_regex`: council, board, commission, committee, hearing, workshop...). This is precision
  first: a real meeting with an unusual title is left off the rail rather than a parade shown as a meeting. On
  November 17, 2026 it kept 1,166 of 1,452 recent transcripts.
- **180 days.** It covers the gap since analysis stopped and keeps the table small (about 0.4 MB with indexes). The
  rail only needs the newest few, and a `dbt_utils.recency` warning fires when nothing in it is newer than 14 days.
- **Only the unfiltered recent list.** Topic, theme and question filters are keyed on analyzed meetings
  (`meeting_topic_link`, `meeting_question_link`), so filtered lists stay analyzed-only.
