---
pr: 872
branch: feat/852-where-you-stand-game
title: "feat(web_app): add the Where Do You Stand? game screens"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: e64fba867aecc907ce1720bfce811800b73c226b
verdict: approve-with-nits
---

# PR Review: feat(web_app): add the Where Do You Stand? game screens

## Summary

Adds the "Where Do You Stand?" game at `/play/:packId`: rounds of a chart, its finding as the headline, a statement
and three answers, then a reveal of how people who played answered nationally, in the player's state and in their
community, with groups under the minimum sample withheld. Desktop rounds are scroll-driven pinned acts; phones and
reduced motion get stacked panels. Unit tests, type check and build pass, and the flows were exercised in a browser
against a fixture served through request intercepts. It has not been run against the real API and database.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/package-lock.json`
- `web_app/package.json`
- `web_app/src/App.tsx`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/stance.ts`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/Cover.tsx`
- `web_app/src/components/stance/EndPanel.tsx`
- `web_app/src/components/stance/Odometer.tsx`
- `web_app/src/components/stance/PlaceControl.tsx`
- `web_app/src/components/stance/ProgressRail.tsx`
- `web_app/src/components/stance/ResultBars.tsx`
- `web_app/src/components/stance/RoundPanel.tsx`
- `web_app/src/components/stance/useStanceActs.ts`
- `web_app/src/pages/DataCenters.tsx`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/pages/WhereYouStand.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/stanceGame.test.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_app/src/utils/stancePlayer.ts`
- `web_docs/docs/guides/where-you-stand-game.md`

## CI Status

See the PR checks on `e64fba867aec`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. No seeded answers or example percentages; an empty database shows no split anywhere; findings and chart figures come from API responses; a share is shown only when the endpoint returns whole-scope counts. The player id is a random UUID in local storage and nothing else about the player is kept. The fixture lives outside the repo.

## Strengths

- The "not a poll" wording is on every reveal and the end screen, and the copy never says "residents".
- A review of the first screenshots found group headings taking percentages of only the dots drawn; that was fixed
  before this PR, with a test that headline and heading numbers agree on a capped list.
- The two new libraries load only with the game's chunk and are torn down on unmount.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not run against the real API. The first real play should be watched: a response field named differently from
  the hand-written types would show as an empty chart or a failed answer.
- Community names are free text matched exactly, so "Tuscaloosa" and "City of Tuscaloosa" form separate groups. The
  suggestions help, but a canonical place list would be better.
- Real touch flings on a phone were not tested; pinned mode is switched off below 768 px for that reason.

### 🔵 Nit (Minor)

- Dots are about 10 px, below the 24 px target size; arrow keys, tooltips and the data table are the alternative.
- The commit's co-author trailer names a different model from the one this session's attribution rule gives. It could
  not be amended after the push (history rewrite refused). No effect on the code.
- The design page from #853 still lists the game screens as future work.

## Verdict

**approve-with-nits**
