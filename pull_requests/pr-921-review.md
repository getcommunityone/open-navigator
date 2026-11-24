---
pr: 921
branch: feat/915-story-opens-with-question
title: "feat(web_app): open the Data Center Story on its question, record the vote before and after, and make phones kinetic"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 40f94d270b216f7fcf80d5e6517cc9befd3d2d6f
verdict: approve-with-nits
---

# PR Review: feat(web_app): open the Data Center Story on its question, record the vote before and after, and make phones kinetic

## Summary

The Data Center Story now opens on its question (Yes, No, Pause for now), sets the scope, tells the record with shorter copy, and asks again at the end, storing both votes in a new runtime table and showing before and after results with the minimum-sample rule. Phones get snap scrolling with enter, exit and title animations where they had a plain stacked page; a floating bar keeps a primary next in view; game energy is confined to the challenge. Read by the coordinator against the diff, the agent's report and phone and desktop screenshots.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `api/routes/stance.py`
- `api/stance_packs/data_centers.json`
- `tests/test_stance_api.py`
- `web_app/src/api/stance.ts`
- `web_app/src/components/stance/ChoiceBars.tsx`
- `web_app/src/components/stance/Cover.tsx`
- `web_app/src/components/stance/EndPanel.tsx`
- `web_app/src/components/stance/FloatingNext.tsx`
- `web_app/src/components/stance/KineticText.tsx`
- `web_app/src/components/stance/ProgressPips.tsx`
- `web_app/src/components/stance/RoundPanel.tsx`
- `web_app/src/components/stance/ScopeBar.tsx`
- `web_app/src/components/stance/ScreenNav.tsx`
- `web_app/src/components/stance/SoundToggle.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/StoryVoteScreens.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/pages/Challenge.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/floatingNext.test.ts`
- `web_app/src/utils/floatingNext.ts`
- `web_app/src/utils/storyQuestion.test.ts`
- `web_app/src/utils/storyQuestion.ts`
- `web_docs/docs/development/where-you-stand-game-design.md`
- `web_docs/docs/guides/data-center-challenge.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- Queries are parameterized, the choice is validated against the pack (422 otherwise), and the table declares a primary key and a unique key; it has no foreign keys because it references a pack file, not a table. Like public.stance_response it is created by the API at run time, outside dbt, which CLAUDE.md's key rule tolerates only as a runtime-owned exception; worth recording in the design page if it is not already.
- A reader's before answer is re-saved with the place they pick later. This is deliberate and tested, and it means one reader counts under their latest place only.
- Tested with touch emulation in headless Chromium; a real phone, iOS Safari in particular, is unverified.
- Nobody has heard the sound cues.
- A phone screenshot taken mid-swipe showed the page about 28px low; not chased.
- The Analysis page has the same phone gap: #920.
- No counts are seeded; a withheld split shows its real count and the threshold.

## Verdict

**approve-with-nits**
