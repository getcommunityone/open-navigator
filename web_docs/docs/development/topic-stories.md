---
title: Topic stories (short-term rentals)
description: Data stories told from one curated topic's transcript record — the first is short-term rentals — and the endpoint behind their map.
---

# Topic stories (short-term rentals)

Issue: [#1013](https://github.com/getcommunityone/open-navigator/issues/1013). Added 2026-11-25.

## What it is

A topic story tells one curated topic from the meeting record. The first is **short-term rentals**, at
`/stories/short-term-rentals?state=`. Everything on it is counted or quoted. Nothing is estimated.

| Part | Source |
|---|---|
| Headline: "Short-term rentals came up in N meetings across M states" (or "…in N meetings in Alabama") | `GET /api/topics/{id}/states`: distinct meetings per state |
| US pin map; hovering a pin shows the state's newest passage | the same endpoint's `newest` list (verbatim, `<mark>`ed) |
| "What was said": newest meetings, each with its passage, plus Show more | `GET /api/topics/{id}/meetings` (`topic_transcript_link`) |
| "What was decided" | `GET /api/search?types=decisions&topic_id={id}&sort=date_desc`, using the decision search's `ts_headline` snippet |

The headline makes no sentiment claim. The data center story's "America hates data centers" is gated on a speakers'
positions record, which topic stories don't have.

The scope follows the site rule: `?state=` is the filter, the label says which place is shown, and **National** widens
back out. The map always shows every state's own count, with the scoped state highlighted.

## Endpoint

`GET /api/topics/{topic_id}/states?state=` returns `{topic_id, total_meetings, states: [{state_code, state, meetings}],
newest: [TopicMeeting]}`. It reads `topic_transcript_link`, which is on the hosted copy.

## Browse topics

The home page's Browse topics lists the topic stories in the owner's order:

1. Short-term rentals (live)
2. Flock
3. License plate readers
4. Bike lanes

Only live stories link. The others say "Coming soon". A new story goes live by adding an entry to `TOPIC_STORIES` in
`web_app/src/pages/TopicStory.tsx` (topic id, title, lede) and its route, then setting `to` on its Browse topics card.
Flock and license plate readers currently share topic 100004. They need their own keyword sets before each gets a
separate story.
