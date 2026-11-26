---
sidebar_position: 63
title: Story captions
description: How each topic story and Browse topics tile picks the strongest true statement for its place, the thresholds behind each rule, and why (#1125).
---

# Story captions

[#1125](https://github.com/getcommunityone/open-navigator/issues/1125). The owner (26 Nov 2026) asked for a compelling
caption for every topic: lead with disagreement where it is high-volume, and otherwise with high volume where states
differ. Only the data-center story had a conclusion ("America hates data centers."); the rest said "X talked about Y in N
meetings." or showed a fixed blurb.

## Decision: one picker, five rules, real counts only

`pickCaption(topic, facts, scope)` in `web_app/src/utils/storyCaption.ts` returns `{kind, template, place, basis, ai}`. The
story title on `/stories/<topic>` (`DataStory.tsx`, `TopicStory.tsx`) and each tile on the home **Browse topics** strip
(`HomeTopicStrip.tsx`) use it, scoped to `?state=&city=`. `facts` comes from
`GET /api/topics/{topic}/caption-facts?state=&city=` (`api/routes/topic_caption_facts.py`). The picker ignores facts for
any scope other than the one shown, so the scope label and the numbers always match.

The rules, in order. Each needs its own counts and otherwise falls through to the next (CLAUDE.md, No Fabricated Data):

| # | Kind | Statement | Source |
|---|------|-----------|--------|
| 1 | `disagreement` | Officials sided against the public in N meetings; or speakers split for and against | `data_center_meeting_lean` / `topic_meeting_lean` (AI reading); `data_center_meeting_position` (counted) |
| 2 | `sentiment` | The story's speaker gate ("America hates data centers."); else the public leaned one way in N meetings | `STORIES[...].conclusion`; the lean marts (AI reading) |
| 3 | `state_gap` | The place leads the other states (or places in its state), by meetings or per resident | browse transcript-count marts, `data_center_meeting_mention`, `jurisdictions.population` |
| 4 | `volume` | The place took up the topic in N meetings | same |
| 5 | `question` | The topic's question | none |

AI readings (Jev's screens of the transcripts) are labelled **AI reading** next to the basis line, and the basis says "a
reading of what was said, not a vote count".

## Thresholds and why

| Constant | Value | Why |
|----------|-------|-----|
| `DISAGREEMENT_MIN_MEETINGS` | 10 | Ten separate meetings is a pattern, not one heated night. Nationally 23 data-center meetings pass (10 states); Georgia passes alone with 11. |
| `SPLIT_MIN_SPEAKERS_PER_SIDE` | 10 | The same floor as the data-center headline's `minSpeakers`, applied to each side. |
| `SPLIT_MIN_MINORITY_SHARE` | 0.35 | Below about a third the smaller side is a minority, and the stance is lopsided (rule 2), not split. |
| conclusion gate | ratio 2, 10 speakers | Unchanged from #989 (`STORIES['data-centers'].conclusion`). |
| `PUBLIC_LEAN_MIN_MEETINGS` | 20 | Enough meetings that the AI reading is a pattern across a state. |
| `PUBLIC_LEAN_MIN_SHARE` | 0.25 | A quarter of the meetings read. Nationally 283 of 1,828 (15%) fails; Georgia 37 of 118 (31%) passes. |
| `STATE_GAP_MIN_RATIO` | 1.5 | A national caption names a state only when it is clearly ahead; at 1.13 (guns: CA 659, NC 585) "more than any other state" is true but not a difference worth leading with. "More than twice" is said only at a ratio of 2 or more. |
| `STATE_GAP_MIN_MEETINGS` | 50 | A lead built on a handful of meetings is noise. |
| `STATE_RANK_MAX` | 3 | "The 2nd / 3rd most of any state" is worth saying; 7th is not. A tie gives no rank. |
| `PER_CAPITA_MIN_MEETINGS` | 100 | Per resident is used only when the raw lead is not clear. Small states with few meetings would otherwise lead on tiny counts. |
| `PER_CAPITA_MIN_RATIO` | 1.5 | Same reason as the raw ratio. |
| `PLACE_GAP_MIN_MEETINGS` | 10 | A city is ranked among its state's places only with ten meetings or more, and only when strictly ahead of the next place. |

Population is on record: `jurisdictions.population` for the 50 states, DC and Puerto Rico. Every state-gap basis says that
how many meetings are on record varies by state, because coverage, not only interest, drives the counts.

## Where the counts come from

- **Data centers:** meetings are distinct `video_id` in `data_center_meeting_mention`, the figure the Data Center Story
  already shows; speakers from `data_center_meeting_position`; AI readings from `data_center_meeting_lean`.
- **Other topics:** `browse_transcript_count`, `browse_entity_state_transcript_count` and
  `browse_entity_place_transcript_count` (entity_type `topic`). For curated topics these equal the distinct meetings in
  `topic_transcript_link`, the same counts `/api/topics/{id}/states` serves the story map.
- **AI readings for other topics:** `topic_meeting_lean` (#1126, one row per meeting and topic). The route reads it in its
  own try block: until it lands, every reading is null and rules 1 and 2 fall through, with no code change needed after.
- Each optional read (population, speakers, lean) is wrapped on its own; a missing table or column gives null, never 0.

## Topics

Strip card to caption key: Data centers `data-centers`; Short-term rentals `short-term-rentals`; Flock `flock` and License
plate readers `license-plate-readers` (both read the curated topic "Flock and license plate readers", so the Flock card
says "Flock and plate-reader cameras"); Guns `guns`; Pickleball `pickleball`; Bike lanes `bike-lanes` (the CivicSearch
topic "Bicycle transportation", named as such); Starting a nonprofit and Insurance shopping are guides with no meeting
record, so they always ask their question and the tile keeps its blurb. Insurance is not linked to the CivicSearch topic
"Insurance discussions": a meeting about insurance is not evidence about shopping for it, so the guide does not borrow that count.

National captions on 26 Nov 2026 (local warehouse):

- Data centers: "In 23 meetings across America, officials backed data centers while the public pushed back." (AI reading)
- Short-term rentals: "California took up short-term rentals in 570 meetings, more than any other state."
- Flock / license plate readers: "California weighed ... in 228 meetings, more than twice any other state."
- Guns: "South Dakota took up guns in 239 meetings, the most per resident of any state."
- Pickleball: "California brought up pickleball in 446 meetings, more than any other state."
- Bike lanes: "California took up bicycle transportation in 687 meetings, more than any other state."
