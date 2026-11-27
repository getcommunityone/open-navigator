---
sidebar_position: 39
title: Story statements and where you sit
description: Why the agree/disagree statements moved from the Data Center Challenge into the Data Story, and how the reader is placed among readers and meeting speakers (#981).
---

# Story statements and where you sit

[#981](https://github.com/getcommunityone/open-navigator/issues/981). The owner (25 Nov 2026): "I like this agree /
disagree / no opinion when we show controversial things. Let's do that instead of having a separate challenge. After they
click their answer we need to give some sort of indicator of where they sit on the continuum of comments' answers."

## Decision: one experience, statements in the story

The Data Center Challenge repeated the story's charts to ask seven statements. Now each statement is asked on the story
screen whose record it is about, under the headline. `/challenge/:packId` and `/play` redirect to `/stories/:packId`,
keeping the place.

- **Where it is set:** in the pack (`api/stance_packs/data_centers.json`). Each statement names its screen in
  `story_screen`, and `validate_pack` rejects two statements on one screen.
- **Mapping:** Sites ← "My area already has enough data centers"; Proposals ← "A data center that meets the rules should
  be allowed near homes"; Promises ← "The jobs … are worth what it asks"; Concerns ← "Water and power use should decide …";
  Meetings ← "Local officials discuss data centers enough …"; Agendas ← "The public gets enough notice …"; Gatherings ←
  "Residents get a real say …".
- **Answers:** stored where they always were (`stance_response`, anonymous player id). Earlier Challenge answers show
  as the reader's own.
- **Empty screens:** a screen with no record for the place asks nothing.
- **Retired code:** the Challenge page and its own components (`RoundPanel`, `EndPanel`, `Cover`, `ResultBars`,
  `useAskTimer`) are removed.

## Decision: where you sit, and only where it's honest

After an answer, two lines can appear. Each is real counts with a **You** marker and the same fact in a sentence.

1. **Readers.** The split of Agree, Not sure and Disagree, from the most specific place that has reached the minimum
   sample (place, then state, then country). Below the minimum, only the count so far is shown, with the number
   needed. Small groups are never split.
2. **Speakers at meetings.** This appears only when agreeing clearly lines up with one side of the people who spoke at
   the meetings, recorded per statement as `speaker_lean`:
   - *for*: "jobs are worth it", "allowed near homes";
   - *against*: "my area already has enough".

   Statements about process ("officials discuss enough", "enough notice", "a real say", "water and power should
   decide") have no lean. Placing those answers among speakers for or against data centers would be an invented
   alignment, so no speaker line is shown for them.

   The bar runs from **Spoke for** through **asked a question or took no side** to **Spoke against**, from the scope's
   speaker counts. **Not sure** sits in the middle.

The maths lives in `web_app/src/utils/stanceContinuum.ts`, with tests. The block is `StoryStatement.tsx`, and the data
comes from `useStoryStatements.ts`.

Change a lean only with a reason written here: it is an editorial judgment about what an answer means.

## Decision: conclusion headlines, shown only when the record backs them (#989)

The owner (25 Nov 2026) wants every data story to lead with a compelling conclusion as its title, with a subtitle. A
conclusion is a claim, so it is **data-gated**. It shows only while the national speaker record backs it: the side it
names must outnumber the other by at least 2:1, among at least 10 speakers on record. A basis line under it states the
real counts. When the record stops backing it, the story's neutral title shows instead. The gate is
`storyConclusion()` in `web_app/src/utils/dataStory.ts`, with tests.

| Story | Headline | Subtitle | Gate | Today (local warehouse) |
| --- | --- | --- | --- | --- |
| Data centers (live) | America hates data centers. | Public comments don't always match America's true sentiment, but our nation is clearly at a fever pitch of data center opposition. | against ≥ 2 × for, ≥ 10 speakers | 18 against, 3 for, of 29 speakers: shown |

Since #1125 the conclusion is one of the caption picker's rules (see [Story captions](story-captions.md)), and since
[#1182](https://github.com/getcommunityone/open-navigator/issues/1182) a place whose own reading is too thin states the
broader scope's conclusion by name ("America hates data centers; Tuscaloosa, Alabama brought them up in 2 meetings."),
so the title matches the red map beside it. Every story opens with a topic-named **Start the [topic] story →** and
**Next story: [title] →** in its first screen.

### Drafts for topics without a story yet

These are not on the site. Each would need its own story, and a speaker-position record like data centers'
(`data_center_meeting_position`), before its headline could be checked. On 25 Nov 2026 the general `public_comment`
table holds very few comments that name them (matched on the speaker's own words):

| Topic | Draft headline | Draft subtitle | Would need | Comments today |
| --- | --- | --- | --- | --- |
| Short-term rentals | Neighbors want limits on short-term rentals. | Public comments are a slice of a town, not a poll, but the people who come to the microphone keep asking councils to rein in Airbnb-style rentals. | against ≥ 2 × for, ≥ 10 speakers | 2 against, 2 for |
| Flock cameras | Flock cameras are splitting towns. | Safety on one side, surveillance on the other: speakers rarely land in the middle on automated police cameras. | a clear majority either way, ≥ 10 speakers | 2 against, 1 for |
| Bike lanes and paths | Everyone wants safer streets, until the bike lane is theirs. | Support for biking is broad in the abstract; the fights are about one street, one parking lane, one block at a time. | for/against split by meeting, ≥ 10 speakers | none |
| License plate readers | Americans don't want to be tracked by license plate readers. | Comments are not a census of opinion, but speakers keep raising privacy before police get another camera. | against ≥ 2 × for, ≥ 10 speakers | none |

If a topic's record lands the other way, its headline changes to match the record. A headline is never kept against
the data.
