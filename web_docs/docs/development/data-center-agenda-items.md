---
sidebar_position: 35
title: Data center items on agendas
description: How Open Navigator finds data center items on meeting agendas so residents hear about them before the vote (DC-4.2).
---

# Data center items on agendas

[DC-4.2](https://github.com/getcommunityone/open-navigator/issues/250) surfaces data center items on meeting agendas,
upcoming meetings first, so residents can attend the meeting where a site is decided. It is part of the
[Data Center Accountability epic](https://github.com/getcommunityone/open-navigator/issues/236).

## In short

- Agendas are posted before the meeting, so an agenda with a future date is an item residents can still act on.
- An agenda is kept when its text mentions a data center ("data center", "data centre", "hyperscale", "server farm").
- Each item quotes the agenda with the matched words highlighted, and is tagged **Zoning or utility item** when a
  zoning, land-use, tax-incentive or utility word appears within about 250 characters of the mention.
- When the agenda names a [tracked site](./data-center-sites.md) in the same state, the item links to it.
- Coverage follows the agendas whose text we've extracted (today mostly Tuscaloosa, from SuiteOne). More cities come
  with the meeting adapters ([CORE-3.2](https://github.com/getcommunityone/open-navigator/issues/243)).
- Meetings are also searched by what was **said**: transcripts that discuss a data center show under
  **Said in meetings**, each passage quoted with the matched words highlighted and a link to that moment in the
  recording ([#445](https://github.com/getcommunityone/open-navigator/issues/445)). This reaches the many places whose
  agendas we don't have yet.

<details>
<summary>Where each piece lives</summary>

| Step | Where | What it does |
|---|---|---|
| Mart | `data_center_agenda_item` (public) | One row per agenda that mentions a data center. PK `data_center_agenda_item_id`; FKs to `event_meeting_document`, `jurisdictions`, `data_center_site`. `evidence` is a `ts_headline` excerpt with `<mark>` around the matched words |
| API | `GET /api/data-centers/agenda-items?state=&city=&when=upcoming\|past\|all` | Upcoming first (soonest first), then past (newest first). `is_upcoming` is worked out from today, so a table built last week can't call a past meeting upcoming |
| Page | `/data-centers?state=&city=`, "On the agenda" | "Coming up" and "Earlier meetings", each with the meeting, date, quote, tags and agenda link |
| Mart | `data_center_meeting_mention` (public) | One row per (transcript video, passage). PK `data_center_meeting_mention_id` = md5(`video_id\|passage_index`); FKs to `jurisdictions` and `data_center_site` (both nullable). `evidence` is a `ts_headline` excerpt of the passage; `start_seconds` is the moment to jump to |
| Intermediate | `int_data_center_transcript__passage`, `int_data_center_site__jurisdiction` | Passages (~3-minute windows of timed cues, or 2,500-character windows when untimed) that say a data center word; the governments around each site (meeting-source survey, address city, its county) |
| API | `GET /api/data-centers/meeting-mentions?state=&city=&site_id=&strength=` | Newest meeting first; `counts` are real totals for the scope; `jump_url` opens the recording at the passage |
| Page | `/data-centers?state=&city=`, "Said in meetings" | One card per meeting with its quoted passages and "Watch at m:ss" links |

</details>

<details>
<summary>Decisions and why</summary>

- **Word match, not AI.** A plain text match is cheap, runs in dbt on every build, and its evidence is the agenda's own
  words. A false positive (a staff report that only mentions data centers) is visible as such from the quote, and the
  zoning-or-utility tag is what marks the items that are likely decisions.
- **The 250-character window** is a PostgreSQL limit (a regex repeat count can't exceed 255). It is close enough to
  "the same agenda item" for typical agendas.
- **No quote, no item.** A document whose text doesn't produce a highlighted excerpt is left out, per the site-wide
  match-evidence rule.
- **Site links need the site's name in the same state**, and names shorter than 6 characters are skipped, so a
  common word can't create a link.
- **Transcripts get a sibling model, not a source type on the agenda mart** (#445). The agenda mart is one row per
  agenda document with a NOT NULL key to `event_meeting_document`; a transcript has many passages and no meeting
  document, so mixing them would loosen that key.
- **A passage is about three minutes of speech.** Long meetings mention a data center many times; one row per
  passage keeps each quote short enough to read and gives each one its own moment in the recording.
- **The transcript's own words, never its metadata.** A passage is kept only when its text says "data center",
  "data centre", "datacenter" or "hyperscale" and the highlight finds it. Titles and descriptions don't count.
- **Owner names count only near the site.** "Google" or "Meta" in a passage marks it `site_specific` only when the
  meeting's government is one of the governments around that company's site; a site or project name (6+
  characters) counts anywhere in the site's state.
- **`has_transcript` is not trusted.** About 10,000 transcripts loaded between 2026-05-31 and 2026-06-10 carry full
  captions with `has_transcript = false` (Minneapolis's 2026-05-21 council meeting among them), so the model checks
  the text itself.

</details>
