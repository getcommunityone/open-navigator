---
pr: 877
branch: feat/859-matrix-story-house-theme
title: "feat(web_app): tell the Matrix map as five chapters in the house theme"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: b9da9c834533102ee59866ecabd29e788a4ae846
verdict: approve-with-nits
---

# PR Review: feat(web_app): tell the Matrix map as five chapters in the house theme

## Summary

Makes the Matrix map a five-chapter story with a public-meeting metaphor, defaults it to a new "Open Navigator"
theme in the product's colours, turns each section's headline into a sentence computed from the data in scope, ends
with a call to action, and brings the title animation in line with the reference. Unit tests, type check and build
pass; the chapters and sections were looked at in a browser against a throwaway fixture. Not seen with real census
data.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/src/components/matrix/ActionBlock.tsx`
- `web_app/src/components/matrix/BarsSection.tsx`
- `web_app/src/components/matrix/ChapterCard.tsx`
- `web_app/src/components/matrix/ColumnsSection.tsx`
- `web_app/src/components/matrix/CompareSection.tsx`
- `web_app/src/components/matrix/DivergingSection.tsx`
- `web_app/src/components/matrix/DotsSection.tsx`
- `web_app/src/components/matrix/HeatmapSection.tsx`
- `web_app/src/components/matrix/PivotSection.tsx`
- `web_app/src/components/matrix/ScatterSection.tsx`
- `web_app/src/components/matrix/SectionBand.tsx`
- `web_app/src/components/matrix/SectionShell.tsx`
- `web_app/src/components/matrix/ShareSection.tsx`
- `web_app/src/components/matrix/TableSection.tsx`
- `web_app/src/components/matrix/TilesSection.tsx`
- `web_app/src/components/matrix/TitleBlock.tsx`
- `web_app/src/components/matrix/TrendSection.tsx`
- `web_app/src/components/matrix/data.ts`
- `web_app/src/components/matrix/hooks.ts`
- `web_app/src/components/matrix/types.ts`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/styles/folio.css`
- `web_app/src/utils/folioRamp.test.ts`
- `web_app/src/utils/folioThemes.ts`
- `web_app/src/utils/matrixStory.test.ts`
- `web_app/src/utils/matrixStory.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `b9da9c834533`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. Story sentences are pure functions of the section's data, fall back to a neutral description when a figure is missing, and are tested against a list of banned judgment and cause words. No sample copy from the reference is reused.

## Strengths

- The story copy is testable: 31 cases cover present, missing, tied, single-geography and lower-is-better data.
- The new theme is held to the same contrast checks as the others, plus a colour-vision separation test.
- The title animation was measured frame by frame against the reference before changing it; the real differences
  (late trigger, fixed line breaks) were fixed and the timings left alone because they already matched.
- Every action link was checked against the routes in `App.tsx`.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not seen with real census data. Sentences built from real values may read awkwardly in cases the fixture did not
  produce (long place names, many-way ties). The owner should scroll the page once and report any that do.
- On a tie the lead names both geographies while a later line in the same section names one. The two should agree.

### 🔵 Nit (Minor)

- Chapter cards are tall, up to about 60% of the viewport, with a lot of empty space.
- The series palette's muted red is the hue also used for "worse".
- `TableSection.tsx` has un-reindented JSX inside a new fragment.

## Verdict

**approve-with-nits**
