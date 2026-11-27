---
title: Topic stories, screen by screen
description: Why the topic stories share the Data Center Story's screen machine, which screens a topic gets, and what was left out (#1224).
---

# Topic stories, screen by screen

[#1224](https://github.com/getcommunityone/open-navigator/issues/1224). Added 2026-11-26. Owner: "All the stories
should have horizontal scroll drill down with swipe like data center."

## Decision

Topic stories (`TopicStory.tsx`) use the Data Center Story's screen machine instead of a long page. The machine was moved
out of `DataStory.tsx` unchanged into `components/stance/useStoryScreens.ts` (landing on `?screen=`, writing the screen in
view back to the URL, the cover hold, keyboard paging, focus on the settled screen's heading), and one screen's markup into
`components/stance/StoryScreenFrame.tsx`, which `StoryScreenView` now renders. A copy would have drifted; both pages now
move, announce and focus alike, and `e2e/story-nav.check.mjs` checks both.

## Which screens

`utils/topicStoryScreens.ts` holds the list (Overview, Over time, Who spoke, Companies, What was said, Decisions, Recap)
and `planTopicScreens`, which drops a screen whose data loaded empty and records why for the cover's note. Overview and
Recap always stay. Nothing on a screen is invented to fill it: an empty screen goes, a loading one says it is loading.

## What was left out, and why

- **County drill-down and box transition** (#1195): the topic endpoints count meetings by state only. Adding a county
  grain needs a jurisdiction-to-county count for `topic_transcript_link`; until then the Overview says there is no county
  view.
- **Unit matrix "By who spoke"**: needs one record per meeting with its AI reading; `/api/topics/{id}/state-map` and
  `caption-facts` serve counts. The Who spoke screen draws the counts as bars in the topic's words.
- **A closing vote**: only the data center pack has a question; the Recap ends on Next story.
- **City grain**: #1186.

## Swipe

`hooks/useSwipeNav.ts` turns a quick sideways flick (at least 50px, 1.5 times its vertical travel, under 800ms) into
Next/Back with passive listeners, so the browser's own vertical scroll and snap keep working. It is used by the topic
stories; the Data Center Story can take the same hook.
