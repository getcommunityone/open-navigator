---
pr: 857
branch: fix/856-lazy-matrix-page
title: "fix(web_app): load the Matrix map page only when its tab is opened"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: e401b45b0df6a68d85ad6baade9cde08c0122367
verdict: approve-with-nits
---

# PR Review: fix(web_app): load the Matrix map page only when its tab is opened

## Summary

The Matrix map page was imported eagerly, so a package missing after a pull blanked every route. The PR makes the
page lazy behind a boundary that shows a loading state and, on failure, a message in its place. Small; the message
is unit-tested and the build emits the separate chunk. The failure path was not exercised in a browser.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/src/App.tsx`
- `web_app/src/components/LazyRouteBoundary.tsx`
- `web_app/src/utils/lazyRouteMessage.test.ts`
- `web_app/src/utils/lazyRouteMessage.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `e401b45b0df6`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. The failure message shows the error's own text and says so when there is none.

## Strengths

- The blast radius of the page's dependencies is now its own tab, and its fonts leave the main bundle.
- The boundary is reusable for other heavy pages.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- The boundary was type-checked and built but its failure path was not run in a browser. In development Vite also
  shows its own error overlay for an unresolved import, so the owner may see that overlay on top of the message.

### 🔵 Nit (Minor)

- The boundary does not reset when the route changes; leaving and returning to the tab after a failure still shows
  the message until Reload. Acceptable, since a failed chunk load needs a reload anyway.

## Verdict

**approve-with-nits**
