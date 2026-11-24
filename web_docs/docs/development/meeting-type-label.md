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

Tests: `tests/test_meeting_type_797.py` and `web_app/src/components/storyLensesMeetingType.test.ts`.
