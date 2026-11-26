---
title: Meeting search on the hosted site (meeting passages)
description: Why meeting search has a third source, the verbatim data center meeting passages, and how it stays consistent with the local warehouse.
---

# Meeting search on the hosted site (meeting passages)

Issue: [#1007](https://github.com/getcommunityone/open-navigator/issues/1007). Decision made 2026-11-25.

## Problem

The Meetings results in `/api/search` come from two sources:

1. **Analyzed meetings:** `event_meeting`, the meetings the AI has summarized.
2. **Transcripts:** `event_documents`, every transcribed meeting video not already analyzed. There are about 119,000 locally.

The hosted database (Neon) has a 512 MB cap, so it holds only a small slice of `event_documents`: the 1,664 videos that
are already analyzed meetings. Source 2 adds nothing there. A search for "Data centers" in Alabama found 8 meetings on
the site and 870 locally. Meanwhile the data story counted 71 Alabama meetings where a data center came up.

## Decision

Meeting search gets a third source: **`data_center_meeting_mention`**, the verbatim transcript passages behind the data
story (one row per passage; 1,859 meetings, about 7 MB). That table is already on the hosted database.

- **When it runs:** only with a query or topic filter. It surfaces a matched passage, never a plain browse.
- **What matches:** the passage text, using `to_tsvector('english', evidence)` against the same tsquery as the other
  sources. It applies the same state, city and county filters.
- **No duplicates:** a video already returned by sources 1 or 2 is left out. Locally, where every transcript is present,
  this source adds nothing. On the hosted site it adds the meetings the missing transcripts would have found.
- **What the card shows:** the meeting's matching passages, verbatim, headlined with `<mark>` (the match-evidence rule in
  `CLAUDE.md`), linking to the video. In the results, `metadata.source` is `meeting_passage` (transcript rows say
  `transcript`) and `analysis_pending` is true.
- **Counts:** `count_events` adds the same third source, so the Meetings tab total matches the list.

Shared code: `meeting_passage_where()` in `api/routes/search_postgres.py`, used by `search_events_pg` and
`search.count_events`.

## Rejected

- **Copying the full transcripts to the hosted database:** about 237 MB for the analyzed slice alone, and far more for
  every transcript. That would need a paid Neon plan.
- **A data-center-only search shortcut:** the passages are matched like any other text, so a query such as "fluoride"
  also finds a data center meeting whose passage says it.

## Also in this change

`browse_entity_place_transcript_count` (about 6.7 MB) joins the hosted copy's allow-list. `/api/topics` reads it and
returned 503 on the site without it.
