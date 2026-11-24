---
pr: 892
branch: feat/884-data-stories-and-challenge
title: "feat(web_app): add data stories and rename the game the Data Center Challenge"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: ea1f46570ddea451f0b21823d142cd39a6b34fb7
verdict: approve
---

# PR Review: feat(web_app): add data stories and rename the game the Data Center Challenge

## Summary

Automated review (#648) for PR #892 on `feat/884-data-stories-and-challenge`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/stance_packs/data_centers.json`
- `tests/test_stance_api.py`
- `web_app/src/App.tsx`
- `web_app/src/api/stance.ts`
- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/Cover.tsx`
- `web_app/src/components/stance/EndPanel.tsx`
- `web_app/src/components/stance/PlaceControl.tsx`
- `web_app/src/components/stance/ProgressRail.tsx`
- `web_app/src/components/stance/RoundPanel.tsx`
- `web_app/src/components/stance/ScopeBar.tsx`
- `web_app/src/components/stance/ScreenNav.tsx`
- `web_app/src/components/stance/SentenceHeading.tsx`
- `web_app/src/components/stance/StatRow.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/components/stance/useRecentWrites.ts`
- `web_app/src/components/stance/useScreenKeys.ts`
- `web_app/src/components/stance/useStoryData.ts`
- `web_app/src/pages/Challenge.tsx`
- `web_app/src/pages/DataCenters.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/houseTheme.ts`
- `web_app/src/utils/stanceGame.test.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/development/where-you-stand-game-design.md`
- `web_docs/docs/guides/data-center-challenge.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `ea1f46570dde`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**
