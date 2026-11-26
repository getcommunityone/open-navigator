---
pr: 908
branch: feat/904-scroll-cue
title: "feat(web_app): animated cue that invites the reader to the next screen"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 9163e5a90c4e12f59c1c4a96dd7dcba78a334b31
verdict: approve-with-nits
---

# PR Review: feat(web_app): animated cue that invites the reader to the next screen

## Summary

Adds one ScrollCue component: a button with a falling chevron that appears after two seconds of stillness on a story or Analysis screen that has a next one, named for where it goes, hidden while the page moves, still under reduced motion. Replaces the static first-screen hint on Analysis.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `web_app/src/components/story/ScrollCue.tsx`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/folio.css`
- `web_app/src/styles/scroll-cue.css`
- `web_app/src/utils/scrollCue.test.ts`
- `web_app/src/utils/scrollCue.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`
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

- On a phone the cue sits over the last line of body text until the page moves.
- Checked on the first two screens of each page and the story's last screen, not all of them.
- The challenge cover gets the cue after #899 merges.

## Verdict

**approve-with-nits**
