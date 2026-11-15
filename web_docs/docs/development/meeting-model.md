---
title: One meeting model across platforms
sidebar_label: Meeting model
---

# One meeting model across platforms

Decision record for CORE-3.1, [one meeting model across platforms](https://github.com/getcommunityone/open-navigator/issues/242),
in the [CORE epic: meetings, legislation and officials](https://github.com/getcommunityone/open-navigator/issues/235).
Recorded November 13, 2026.

## What we chose

- **One shape.** Meetings from every broadcast platform become a `Meeting` (`packages/ingestion/src/ingestion/meetings/`).
  Its agenda, recording, transcript and minutes sit in fixed slots, named by `ArtifactKind`, instead of in link
  titles that must be matched by wording. A transcript can be a link or the text itself, because some sources (LocalView's
  YouTube captions) carry the text inline.
- **One adapter per platform.** Each platform has a `MeetingAdapter` whose `normalize(raw)` returns a `Meeting`,
  registered under a platform code. The first two are `youtube`, where a LocalView row gives the recording and its
  captions, and `legistar`, where a Web API event gives the agenda, minutes and video.
- **A loud failure.** `adapter_for(platform_code, jurisdiction_name=...)` raises `UnsupportedPlatformError`, naming
  the platform, the jurisdiction and the platforms that are supported. It never falls back to a generic scraper.
  `coverage_report()` counts the jurisdictions each adapter covers and lists the ones left uncovered, and its `log()`
  warns once per unsupported platform.

## Why

- The existing `MeetingEvent` (`packages/datamodels/models/meeting_event.py`) finds an agenda or a video by matching
  words in link titles, and it has no slot for a transcript. Fixed slots make "this meeting has an agenda" a fact read
  from the source, not a guess from a label.
- `platform_detector.get_scraper_class()` falls back to a `GenericScraper` that doesn't exist yet. So a council on an
  unsupported platform looks like a council with no meetings. Under the No Fabricated Data rule, a silent empty
  result is a false claim. An error that names the gap, and a coverage line in every run, keep it visible.
- A missing artifact stays `None`. A LocalView row has no agenda, so its meeting has none, and a page shows an empty
  state for it instead of inventing one.

## What we didn't change

- `MeetingEvent` and its callers are untouched. A later story can move storage onto `Meeting.to_record()`, which
  gives every platform the same columns, keyed by `meeting_key`.
- No table, API or UI changes in CORE-3.1. CORE-3.2,
  [adapters for the baseline councils](https://github.com/getcommunityone/open-navigator/issues/243), connects real
  councils to these adapters.

## When to revisit

- When CORE-3.2 adds the baseline councils' platforms.
- When a platform carries something the four artifact kinds can't hold.
