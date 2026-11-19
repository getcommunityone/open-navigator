---
sidebar_position: 46
title: Meeting platform readers (Granicus and Legistar)
description: How Open Navigator reads meetings from Granicus portals and the Legistar Web API, what lands in bronze, and why Granicus pages are not fetched.
---

# Meeting platform readers (Granicus and Legistar)

Issue #536 (epic #530). Most local governments publish their meetings on Granicus and
Legistar, not on YouTube. The package `scrapers.platforms` reads both and lands every
meeting in bronze.

## What runs

```bash
# dry run: the #460 survey's portals, then 20 more Legistar portals found by URL pattern
python -m scrapers.platforms.run --data-center --pattern-target 20
# write to the local warehouse
python -m scrapers.platforms.run --data-center --pattern-target 20 --apply
# one portal
python -m scrapers.platforms.run --legistar-client dakota --jurisdiction-id dakota_27037 --apply
# the Colab Whisper queue (#489) as TSV
python -m scrapers.platforms.run --export-whisper-queue data/cache/platform_meetings/whisper_queue.tsv
```

| Module | Reads |
|---|---|
| `scrapers.platforms.legistar` | `webapi.legistar.com/v1/<client>/events`, then `/events/<id>/eventitems` for the agenda items and minutes notes |
| `scrapers.platforms.granicus` | `<host>/ViewPublisher.php?view_id=N`, its RSS, and the caption track a `MediaPlayer.php` page links |
| `scrapers.platforms.discover` | portals from `bronze_jurisdiction_meeting_source` (#460), then Legistar client slugs by URL pattern |
| `scrapers.platforms.store` | idempotent upserts into the bronze tables below |

## Bronze

- `bronze.bronze_platform_meeting`: PK `(platform, meeting_uid)`. One row per meeting,
  with its date, body, title, agenda, minutes and video URLs, the agenda and minutes
  text the platform serves, and `transcription_status`.
- `bronze.bronze_platform_meeting_caption`: PK `(platform, meeting_uid)`, FK to the
  meeting. Caption text and `{start, duration, text}` cues.
- `bronze.bronze_platform_portal`: PK `(platform, portal)`. Each portal read or probed
  has a status: `ok`, `empty`, `robots_disallowed`, `blocked`, `not_configured`,
  `token_required` or `error`. A portal that couldn't be read is recorded, not dropped.

Re-runs update rows in place. A Legistar meeting whose `EventLastModifiedUtc` hasn't
changed is skipped, and its event items are not fetched again.

## Where it flows

- `stg_bronze_platform_meeting`, `stg_bronze_platform_meeting_caption`: typed staging.
- `stg_platform_meeting_documents` goes into `event_meeting_document` as its third
  source (`source` = `legistar` or `granicus`). Its `content` is the platform-served
  agenda or minutes text, so `data_center_agenda_item` and document search read it.
- `stg_bronze_platform_meeting_caption` goes into `event_documents` as a `transcript`
  whose `video_id` is `'<platform>:<meeting_uid>'`.
- `platform_meeting` (gold): one row per meeting, FK `jurisdiction_id` to `jurisdictions`.
- `stg_platform_meeting__whisper_queue`: videos without captions (`queued_whisper`).

## Decisions

**robots.txt is obeyed, so Granicus pages are not read (2026-11-17).** Every Granicus
host in the #460 survey serves `User-agent: *` / `Disallow: /`, which lets in only named
search engines. The Legistar document hosts (`<client>.legistar1.com`,
`legistar*.granicus.com`) serve the same rule. The reader therefore fetches only
robots.txt from those hosts and records the portal as `robots_disallowed`. It doesn't
change its user agent, and it doesn't go around bot protection (#443). For a government
on both platforms, its Granicus meetings still arrive through the Legistar Web API,
which has no robots.txt. The Legistar event carries the Granicus clip id, which becomes
the video URL on the government's known Granicus host (`video_url_source='granicus_clip'`).

**Agenda and minutes text comes from the API, not from the PDFs.** The PDFs are on
disallowed hosts, so only their URLs are kept. The text comes from the Legistar event
items: item titles and agenda notes for the agenda; minutes notes (RTF converted to
plain text), actions and vote results for the minutes.

**Captions are read only where the platform serves them and robots.txt allows it.**
Legistar serves no captions. A video without captions is marked `queued_whisper` for
the Colab Whisper runner (#489) and is never transcribed here. Before that runner
downloads a video, it must check the video host's robots.txt.

**A Legistar portal found by URL pattern counts only when it is confirmed.** The Web
API must serve the slug, and the slug's calendar page must name the government and its
state. Granicus portals aren't found by URL pattern, because a disallowed page can't
confirm whose portal it is.
