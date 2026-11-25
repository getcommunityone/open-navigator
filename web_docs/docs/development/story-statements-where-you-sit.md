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
