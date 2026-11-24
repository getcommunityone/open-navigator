---
pr: 925
branch: fix/924-local-meetings-copy
title: "fix(web_app): say local meetings in the Data Stories and challenge copy"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: b7dfedd176fab5f9573378200e93ed20d2d6fb22
verdict: approve-with-nits
---

# PR Review: fix(web_app): say local meetings in the Data Stories and challenge copy

## Summary

Copy only: public meetings becomes local meetings in the hub card, the story's last screen and promises screen, one challenge chart title and two sentences of the challenge guide, at the owner's request.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `web_app/src/components/stance/StoryVoteScreens.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/guides/data-center-challenge.md`

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

- Not viewed in a browser; each change swaps one word for another of similar length inside existing text.
- Code comments still say public meeting; they are not reader-facing.
- Other pages of the site (home, events) still say city council and public hearings; out of scope here.

## Verdict

**approve-with-nits**
