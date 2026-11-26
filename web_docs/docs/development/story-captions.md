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

## Decision: one title, five rules, real counts only

`pickCaption(topic, facts, scope)` in `web_app/src/utils/storyCaption.ts` returns `{kind, template, place, basis, ai}`. The
template keeps the place and topic as blanks, so one title serves the story header on `/stories/<topic>` (`DataStory.tsx`,
`TopicStory.tsx`), the home story card (`HomeDataStories.tsx`) and each tile on the home **Browse topics** strip
(`HomeTopicStrip.tsx`), all scoped to `?state=&city=`. `facts` comes from
`GET /api/topics/{topic}/caption-facts?state=&city=` (`api/routes/topic_caption_facts.py`). The picker ignores facts for
any scope other than the one shown, so the scope label and the numbers always match.

The owner (26 Nov 2026) wants the conclusion style as the one title: "[Place] hates [topic]." or "[Place] is divided on
[topic].", and the record's volume otherwise. The rules, in order; each needs its own counts and otherwise falls through
(CLAUDE.md, No Fabricated Data):

| # | Kind | Title | Needs | Source |
|---|------|-------|-------|--------|
| a | `sentiment` | "[America] hates [data centers]." | Confident public-against meetings at volume (AI reading), or the counted-speaker gate | `data_center_meeting_lean` / `topic_meeting_lean`; `data_center_meeting_position` |
| b | `disagreement` | "[America] is divided on [data centers]." | Officials sided against the public at volume (AI reading), or counted speakers split | the lean marts; `data_center_meeting_position` |
| c | `state_gap` | "[California] took up [short-term rentals] in 570 meetings, more than any other state." | A clear lead; a near tie names both | browse transcript-count marts, `data_center_meeting_mention` |
| d | `volume` | "[Florida] took up [short-term rentals] in 47 meetings." | Any meetings | same |
| e | `question` | The topic's question | none | none |

The basis line under the title gives the numbers. For (b) it reads "In 23 meetings across 10 states, officials backed data
centers while the public pushed back (AI reading)." Every AI reading says "(AI reading)" in the basis, and a tile (which
shows no basis) is prefixed **AI reading**.

**Only the confident "against" reading is used.** Jev's "for" and "mixed" labels were unreliable in hand checks
([Data center meeting lean](data-center-meeting-lean.md)), so they are never counted and never used in a ratio, and (a) is
a count of confident against-meetings, not a share of meetings read.

**"Hates" only where "against" has one direction.** For data centers, Flock and plate readers, and pickleball, a public
against is against the thing. For guns, short-term rentals and fluoridation the public can be against the thing or against
limits on it, so (a) is skipped for them; (b) still applies, because officials and the public disagreeing needs no
direction.

**No zero clauses.** No title or basis states a zero ("0 spoke for"): a zero clause is left out (owner rule).

**No per-resident claim.** An earlier draft named the state with the most meetings per resident (guns: South Dakota, 268
per million). Meeting coverage varies hugely by state, so a per-resident rate measures our coverage, not the state's
interest. It was dropped. When the top two states are within `STATE_GAP_MIN_RATIO` of each other, both are named: "California
and North Carolina took up guns most: 659 and 585 meetings."

## Thresholds and why

| Constant | Value | Why |
|----------|-------|-----|
| `HATES_MIN_MEETINGS` | 50 national, 10 state, 3 city | Confident public-against meetings before "hates" leads. Fifty across the country, ten in a state and three in one place are each a pattern, not one heated night. Nationally 283 data-center meetings pass; Georgia 37; Arizona 14. |
| conclusion gate | ratio 2, 10 speakers | Unchanged from #989 (`STORIES['data-centers'].conclusion`): counted speakers against at least twice for, at least 10 speakers. Either it or the AI count is enough for (a). |
| `DISAGREEMENT_MIN_MEETINGS` | 10 | Ten separate meetings where officials sided against the public. Nationally 23 data-center meetings pass (10 states), but (a) leads there. |
| `SPLIT_MIN_SPEAKERS_PER_SIDE` | 10 | The same floor as the headline's `minSpeakers`, applied to each side. |
| `SPLIT_MIN_MINORITY_SHARE` | 0.35 | Below about a third the smaller side is a minority, and the stance is lopsided, not split. |
| `STATE_GAP_MIN_RATIO` | 1.25 | A state is named alone only when it leads the next by a quarter or more; below that the two are named together, since a lead of a few percent is within coverage noise. "More than twice" is said only at a ratio of 2 or more. |
| `STATE_GAP_MIN_MEETINGS` | 50 | A lead built on a handful of meetings is noise. Both states of a near tie need it. |
| `STATE_RANK_MAX` | 3 | "The 2nd / 3rd most of any state" is worth saying; 7th is not. A tie gives no rank. |
| `PLACE_GAP_MIN_MEETINGS` | 10 | A city is ranked among its state's places only with ten meetings or more, and only when strictly ahead of the next place. |

Every state-gap basis says that how many meetings are on record varies by state, because coverage, not only interest,
drives the counts.

## Where the counts come from

- **Data centers:** meetings are distinct `video_id` in `data_center_meeting_mention`, the figure the Data Center Story
  already shows; speakers from `data_center_meeting_position`; AI readings from `data_center_meeting_lean`.
- **Other topics:** `browse_transcript_count`, `browse_entity_state_transcript_count` and
  `browse_entity_place_transcript_count` (entity_type `topic`). For curated topics these equal the distinct meetings in
  `topic_transcript_link`, the same counts `/api/topics/{id}/states` serves the story map.
- **AI readings for other topics:** `topic_meeting_lean` (#1126, one row per meeting and topic). The route reads it in its
  own try block: until it lands, every reading is null and rules (a) and (b) fall through, with no code change needed after.
- The route still returns state populations, but the picker no longer uses them (see above).
- Each optional read (population, speakers, lean) is wrapped on its own; a missing table or column gives null, never 0.

## Topics

Strip card to caption key: Data centers `data-centers`; Short-term rentals `short-term-rentals`; Flock and license plate
readers `license-plate-readers` (one curated topic, 100004, so one tile since #1133; `flock` stays an alias); Guns `guns`; Pickleball `pickleball`; Bike lanes `bike-lanes` (the curated topic
from #1131; until it has meetings the tile keeps its blurb. It no longer borrows the CivicSearch "Bicycle transportation"
count, #1133); Starting a nonprofit and Insurance shopping are guides with no meeting
record, so they always ask their question and the tile keeps its blurb. Insurance is not linked to the CivicSearch topic
"Insurance discussions": a meeting about insurance is not evidence about shopping for it, so the guide does not borrow that count.

National titles on 26 Nov 2026 (local warehouse):

| Topic | Title | Basis |
|-------|-------|-------|
| Data centers | America hates data centers. | 283 confident public-against meetings (AI reading); 29 counted speakers, 18 against, 3 for |
| Short-term rentals | California took up short-term rentals in 570 meetings, more than any other state. | next North Carolina, 317 |
| Flock and license plate readers | California weighed Flock and license plate readers in 228 meetings, more than twice any other state. | next Washington, 105 |
| Guns | California and North Carolina took up guns most: 659 and 585 meetings. | ratio 1.13, a near tie; next Ohio, 399 |
| Pickleball | California brought up pickleball in 446 meetings, more than any other state. | next North Carolina, 292 |
| Water fluoridation | America took up water fluoridation in 526 meetings. | top states tied at 45, under the 50-meeting floor |
| Starting a nonprofit, Insurance | the question | guides with no meeting record |
| Bike lanes | none yet | the curated topic (#1131) has no meetings linked, so the tile keeps its blurb |

Once `topic_meeting_lean` (#1126) reaches `public`, (a) and (b) can lead for other topics (gold on 26 Nov 2026 held 34
confident public-against meetings for Flock and license plate readers, under the national floor of 50).
