---
pr: 892
branch: feat/884-data-stories-and-challenge
title: "feat(web_app): add data stories and rename the game the Data Center Challenge"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: ea1f46570ddea451f0b21823d142cd39a6b34fb7
verdict: approve-with-nits
---

# PR Review: feat(web_app): add data stories and rename the game the Data Center Challenge

## Summary

Adds the Data Stories hub (`/stories`), the Data Center Story (`/stories/data-centers`) and renames the game the Data
Center Challenge (`/challenge/data-centers`), with `/play/...` redirecting. Read by the coordinator against the diff
and the screenshots taken with fixture responses; the heuristic scan ran first.

## Scope of Change

- Pages: `DataStories.tsx`, `DataStory.tsx`, `Challenge.tsx` (was `WhereYouStand.tsx`); routes and redirect in `App.tsx`;
  header item in `SiteHeader.tsx`.
- Story logic: `web_app/src/utils/dataStory.ts` with 208 lines of tests; shared pinned-screen hook `useActs.ts`.
- Pack: `api/stance_packs/data_centers.json` version 2, seven statements (the tax-breaks statement is removed, two
  statements now sit beside the concerns chart); `tests/test_stance_api.py` updated.
- Docs: `web_docs/docs/guides/data-stories.md`, `data-center-challenge.md`, and the design note.

## CI Status

Required checks are read on the head commit before merge. Locally: tsc clean, vitest 271 passed, build ok,
`tests/test_stance_api.py` 27 passed.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none found. Every count and chart comes from the existing data-center API calls in
  `web_app/src/api/stance.ts`; a chart with no rows renders "No data available for this chart"; a results split below
  the minimum sample shows the count and "Not enough answers yet".
- Personal data: none added. Destructive changes: none. Answers already stored for the removed statement stay in
  `public.stance_response`; nothing reads them under pack version 2.

## Strengths

- Scope label and data move together: the heading, the "Showing" row and the queries all read `?state=&city=`, and a
  state-level count is labelled with the state even when a city is in view.
- The results panel says "It is not a poll" and names the sample.
- Screens have word titles, Continue and Back; no numbered headers.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- The place and topic pickers sit inside the `h1`, so its accessible name includes picker text. Tracked with the
  shared heading in #887.
- `components/stance/SentenceHeading.tsx` duplicates the one coming in #893; merge them in #887.
- `/play/data-centers` is still linked from `components/matrix/ActionBlock.tsx` and `DataExplorerMatrixPage.tsx`. The
  redirect keeps them working and #893 removes them.
- Not run against the owner's API or warehouse; screens were checked with fixture responses.

## Verdict

**approve-with-nits**
