---
sidebar_position: 61
title: Which transcripts reach event_documents
description: The rules that decide which YouTube caption transcripts become searchable documents, and why each excluded group is left out.
---

# Which transcripts reach event_documents

`gold.event_documents` (served as `public.event_documents`) is the searchable transcript table. Search, the topic and
question links, the meeting browse pages and the recent-meetings feed all read it. This page records which bronze
transcripts become a document and why the rest don't (#533, epic #530).

## The rule

A row in `bronze.bronze_event_youtube_transcript` becomes a document when **its caption text is at least 100
characters**, it is not a policy-pipeline reject or a tombstone, its channel is not junk, and it is not a Canadian
meeting. The models that apply it:

| Step | Model | Filter |
|------|-------|--------|
| 1 | `stg_bronze_event_youtube_transcript` | has caption text (`raw_text` or a non-empty `segments` array); `transcript_source` not `excluded:%` or `tombstone:%` |
| 2 | `events_text_search` | at least 100 characters; one transcript per `video_id` |
| 3 | `event_documents` | not junk-gated; not a Canadian CivicSearch meeting |

## Decisions (November 17, 2026, #533)

**The text decides, not the `has_transcript` flag.** About 10,200 rows loaded between May 30 and June 10, 2026 carry
full captions with `has_transcript = false` (#470). The staging filter used the flag, so meetings such as the
Minneapolis City Council on May 21, 2026 never became documents. Staging now tests the text, the same rule the data
center passages already used (#445). The flag still passes through as a column.

**Junk channels stay out.** Videos on channels that `bronze_youtube_channel_classification` marks `is_junk` or not
`is_government` are removed by the gate in `event_youtube_with_jurisdiction`. `event_documents` used that view only to
fill in titles and places, so 156 junk transcripts (gameplay, vlogs, music videos, a land-sale ad) were searchable.
They are now excluded. Videos with no classification are kept: an unscored channel is never dropped.

**Canadian meetings stay out.** CivicSearch also indexes Canadian municipal meetings (Toronto, Ottawa, Halifax and
others). The jurisdiction model is US-only, so they would appear in national search and in topic and question counts
with no place. They are identified by a CivicSearch `location` that ends in a Canadian province or territory
(macro `canadian_location_regex`). On November 17, 2026 these were exactly the 696 CivicSearch transcripts that
resolved to no jurisdiction.

**Unattributed US videos stay in.** Videos whose reviewed attribution names no government (#514, a citizen-media
channel covering several Georgia governments) keep a NULL jurisdiction and remain searchable.

## Counts on November 17, 2026

| Group | Transcripts | Reason |
|-------|------------:|--------|
| In `event_documents` | 130,741 | meets the rule (was 119,934) |
| No caption text | 45,205 | nothing to search |
| Canadian CivicSearch meeting | 696 | outside the US jurisdiction model |
| Under 100 characters | 234 | too short to be a meeting |
| Tombstone | 159 | captions could not be fetched |
| Junk-gated channel | 156 | not a government channel |
| Policy-pipeline reject (`excluded:%`) | 67 | promo or news segment |
| Loaded after the build started | 106 | picked up by the next build |

The dbt test `assert_event_documents_covers_captioned_transcripts` (severity warn) lists captioned transcripts that
meet the rule but have no document, so a new gap shows up after the next build.
`assert_event_documents_excludes_junk_and_non_us` (severity error) fails if a junk or Canadian transcript is served.
