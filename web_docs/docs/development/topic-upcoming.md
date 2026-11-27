---
title: What's coming up on a topic
description: How the Coming up screen and the home page's What happens next strip find scheduled meetings, public hearings and still-open state bills for a topic and place (#1302), what counts as evidence, what the warehouse has, and what is left out.
---

# What's coming up on a topic

**Issue:** [#1302](https://github.com/getcommunityone/open-navigator/issues/1302) · **Epic:**
[#1300](https://github.com/getcommunityone/open-navigator/issues/1300)

Owner, 27 Nov 2026: "This is particularly important for upcoming events, meetings and legislation, because that is where
we have the greatest impact." A topic story now says what is coming up, when, where and how to take part, and the home
page opens with a strip from the story to it. Everything shown has a real date from today on and a link to the source.
Nothing is estimated, and an empty place says so.

## What counts as an upcoming item

`gold.topic_upcoming` (published as `public.topic_upcoming`) holds one row per item × topic. An item is listed only when
one of three kinds of evidence ties it to the topic (`match_basis`):

| `match_basis` | Source | Evidence shown (`matched_text`) | Link to take part |
|---|---|---|---|
| `agenda_text` | A future agenda (`event_meeting_document`, Legistar) whose text matches the topic's keyword phrases (the same phrases as `topic_transcript_link`) | The agenda's own passage, `<mark>`ed (`ts_headline`) | The agenda PDF |
| `official_notice` | A data center hearing whose official page we fetched and found stating the date with the item (`data_center_hearing.status = 'verified'`) | The page's own passage | The official page |
| `place_discussed_before` | A scheduled meeting (a Legistar calendar row in `platform_meeting`, or a scheduled YouTube livestream: no length yet, date from its title) of a government whose own recorded meeting discussed the topic in the two years before | That earlier meeting's verbatim transcript passage, with its date and recording | The agenda or meeting page, or the livestream |

`place_discussed_before` is the most common, because agendas are rarely posted more than a week ahead. The screen says
so plainly ("Agenda not posted yet. Gwinnett County discussed data centers on Jun 15, 2026:") and quotes the earlier
meeting: the reader sees why the meeting is listed and never a claim that the topic is on its agenda. An earlier meeting
the AI reading marked as having no real item on the topic (`topic_meeting_lean.excluded_no_item` / `no_item`,
`data_center_meeting_lean.dc_outcome = 'no_data_center_item'`) does not count. Livestreams of ceremonies, webinars and
celebrations are left out by title, and a livestream's stored time is not shown (it is when the video was scheduled, not
when the meeting starts).

`kind` is `meeting` or `hearing` (an agenda passage that says "hearing", or a verified hearing notice). `deadline` and
`bill_action` are in the vocabulary for when a source carries them; none does yet.

Freshness: each row has `source_updated_at` (when the source row was last fetched) and `built_at`. The table keeps rows
from its build date on; the API shows only `item_date >= today`, so an item that passes between builds is never shown as
upcoming. PK `topic_upcoming_id` = md5(topic_id | item_key); FKs to `civicsearch_topic`, `platform_meeting`,
`event_meeting_document` and `data_center_hearing`, enforced.

## Still-open state bills

Bills have no future dates in our data, so they are listed apart, dated by their last action: `topic_legislation_bill`
rows with status `pending` or `passed_chamber`, furthest along first, then newest action. Two guards keep a dead or
enacted bill out of "still open" until the status rule is fixed
([#1308](https://github.com/getcommunityone/open-navigator/issues/1308)): the latest action must be from last year or
this one, and it must not say the bill was chaptered, signed or approved by the governor. A city scope reads its state's
bills.

## API

`GET /api/topics/{topic}/upcoming?state=&city=&limit=` (`api/routes/topic_upcoming.py`) returns the items, `counts` per
kind over the whole scope, `pending_bills` (total, the newest action date in our copy, the five furthest along) and,
when the scope has nothing upcoming, `broader`: the count one level up (city → state → national) so the page can say
"Nothing upcoming on record for Georgia" and link to the wider view.

## What the warehouse had (27 Nov 2026)

| Source | Future-dated rows | Freshness |
|---|---|---|
| Legistar agendas (`event_meeting_document`) | 8, none naming a curated topic | Fetched in November 2026 |
| Legistar calendars (`platform_meeting`) | 27 | Fetched November 2026 |
| Scheduled YouTube livestreams (`bronze_event_youtube`, no length yet) | ~40 | Channel scans through late November 2026 |
| Verified data center hearings (`data_center_hearing`) | 5 (AL, AZ, GA, NJ, TX) | Checked 25 Nov 2026 |
| OpenStates events with a related bill | None in the future; our OpenStates copy was last synced 30 Apr 2026 | Stale |
| Scraped meeting pages, SuiteOne/CivicPlus documents | None in the future | Through June 2026 |

Result: 78 items over six topics. Data centers 34 (12 states), guns 13, license plate readers 12, short-term rentals 10,
pickleball 8, water fluoridation 1 (Bargersville, IN). Water fluoridation in Georgia and data centers in Virginia have
none; the screen says so and offers the national view (and Virginia's open data center bills).

## What is left out, and why

- **Hearing dates on state bills.** Our OpenStates copy has events but none in the future tied to a topic bill, and it is
  seven months old. Refreshing OpenStates (and loading its events) would add `bill_action` items.
- **Comment deadlines.** No source states one in a form we can read reliably; agendas that do ("Public Hearing
  scheduled for 12/10/26") only become items when they also name the topic.
- **Unverified hearing leads.** `data_center_hearing` rows that are not `verified` (unsourced lists, failed fetches,
  pages that don't state the date with the item) are never shown.
