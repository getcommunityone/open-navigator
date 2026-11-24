---
pr: 893
branch: fix/883-matrix-story-titles-fit
title: "fix(web_app): turn the census page into \"Explore [measure] in [place]\" that fits one screen"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
head_sha: a80171c4
verdict: approve-with-nits
---

# PR Review: fix(web_app): turn the census page into "Explore [measure] in [place]" that fits one screen

## Summary

Reworks `/data-explorer/matrix` (tab label now "Analysis") so each screen fits the window, every header states a
finding in words, and the reader pages with Continue and Back. Removes the theme selector and the game link. Written
by the coordinator from the diff and the screenshots; the automated review job failed on this PR because the title
contains double quotes (`auto_pr_review.py: error: unrecognized arguments`), which is logged as a follow-up.

## Scope of Change

- Page and sections: `web_app/src/pages/DataExplorerMatrixPage.tsx`, `web_app/src/components/matrix/*`,
  `web_app/src/styles/folio.css`.
- New: `components/story/SentenceHeading.tsx`, `components/matrix/QuestionHeading.tsx`, `ScreenPager.tsx`,
  `utils/matrixSuggest.ts`, `utils/sentenceHeading.ts`, `styles/sentence-heading.css`, with unit tests.
- Story logic: `web_app/src/utils/matrixStory.ts` and its test.
- Labels: `DataExplorerLayout.tsx`, `App.tsx`, `LazyRouteBoundary.tsx`.
- Docs: `web_docs/docs/guides/data-explorer-matrix-map.md`.

## CI Status

Required checks are read on the head commit before merge. Locally, after merging `main`: tsc clean, vitest 308 passed
in 28 files, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: none.
- Fabricated data: none. Headlines are computed from the loaded census bundle; with one vintage loaded the compare,
  trend and stacked screens say so and draw nothing, and no text compares a year with itself.
- Personal data, destructive changes: none.

## Strengths

- The heading names the scope in effect ("Explore poverty rate in the United States") and the band repeats it with a
  "change" control, so label and data stay together.
- No game or story on census figures, as the owner asked: they have no recording or transcript behind them.
- Keyboard paging leaves inputs, tables and scrollable figures alone; snap and title motion are off under reduced
  motion.
- Fixes a sideways page scroll on phones.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- The Data explorer tab bar does not come back on scroll-up; "Top" is the way to it. The site header is always pinned.
- The band label "What changed" sits over the "Side by side" ranked-bars screen, which shows one year.
- Fast typing in the table search can drop characters: #894.
- Two SentenceHeading components now exist (`components/story/` and `components/stance/`); merge in #887.
- Checked with fixture bundles only (four years and one year), not the real census bundle.

## Verdict

**approve-with-nits**
