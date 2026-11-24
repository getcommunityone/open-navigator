---
pr: 872
branch: feat/852-where-you-stand-game
title: "feat(web_app): add the Where Do You Stand? game screens"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: e64fba867aecc907ce1720bfce811800b73c226b
verdict: approve
---

# PR Review: feat(web_app): add the Where Do You Stand? game screens

## Summary

Automated review (#648) for PR #872 on `feat/852-where-you-stand-game`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

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
