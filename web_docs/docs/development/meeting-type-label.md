---
title: Meeting type label
sidebar_label: Meeting type label
---

# Meeting type label (#797)

The decision card, the decision detail page and the meeting page show the meeting type (for example "City Council")
next to the date.

- **Source:** `event_youtube_with_jurisdiction.meeting_type`, read by `video_id` through `event_meeting`. No new dbt model:
  the column already reaches the `public` view.
- **Label:** `api/meeting_type.py` `meeting_type_label()` only fixes capitalization and spacing (`CITY_COUNCIL` becomes
  `City Council`). A blank or `UNKNOWN` value gives no label, so the page omits it. A type is never guessed.
- **API:** `meeting_type` (string or null) on each `GET /api/decisions` item, on `GET /api/decisions/{id}` and on
  `GET /api/meetings/{id}`.
- **UI:** `StoryCard` (`meetingType` on the render card), the decision detail header and the meeting header, each with
  `data-testid="meeting-type"`.
- **Out of scope:** a filter or facet on meeting type.

## Where the type comes from (#831)

The scraper sets `meeting_type` from the video's title when it first loads the video
(`scrapers.youtube.meeting_type.meeting_type_from_title`). The first matching rule wins, on whole words:

| Type | Title names |
|---|---|
| City Council | city council, council meeting |
| Planning Commission | planning, zoning |
| School Board | school board, board of education |
| Committee | committee, subcommittee |
| Commission | commission, commissioners |
| Board | board, trustees, aldermen, selectmen, supervisors |
| Authority | authority |
| Work Session | work session, study session |
| Briefing | briefing |
| Public Hearing | public hearing, hearing |
| Town Hall | town hall |
| Special Meeting | special |
| Workshop | workshop |
| Council | council (any other) |
| Other | none of the above |

Before #831 only the first three rules and "special" and "workshop" existed, as substring checks, so committee
meetings, commissions, work sessions and briefings were stored as `Other`, and "specialist" in a title made a "Special
Meeting". The first three rules still give the answers they gave before, so a video that already had a type keeps it.

A re-scrape does not overwrite `meeting_type`, so rows already stored as `Other` need the re-type command. It is a dry
run unless `--apply` is passed, writes to the local warehouse only (never `NEON_DATABASE_URL`), and changes only rows
whose type is blank, `Other`, `Unknown` or the loader's `YouTube Video` placeholder:

```bash
python -m scrapers.youtube.meeting_type
python -m scrapers.youtube.meeting_type --apply
```

The dry run prints how many videos would get each type. The new type reaches the site after the usual dbt rebuild and
publish. The analysis loader does not depend on this: it already keeps a video typed `Other` when its title names a
meeting (#829).

Tests: `tests/test_meeting_type_797.py` and `web_app/src/components/storyLensesMeetingType.test.ts`.
