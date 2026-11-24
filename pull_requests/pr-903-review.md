---
pr: 903
branch: fix/898-data-stories-place-picker
title: "fix(web_app): Data Stories place picker is a dialog with one search box and a close button"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 2050acb79b0f458a22a463e806598ecc1066afcd
verdict: approve-with-nits
---

# PR Review: fix(web_app): Data Stories place picker is a dialog with one search box and a close button

## Summary

Replaces the Data Stories place panel with a dialog: close button, one search box for city, county or ZIP, pick-to-apply, one-click national, state and my-location choices, bottom sheet on phones. It calls the home page's resolver functions in `utils/resolvePlace.ts` and leaves `AddressLookup` and the home page untouched. `PlaceControl` props are unchanged.

Read by the coordinator against the diff and screenshots; the heuristic scan ran first.

## Scope of Change


- `web_app/src/components/stance/PlaceControl.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/placeScope.test.ts`
- `web_app/src/utils/placeScope.ts`
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

- The shared resolver does not filter business or street results for free text the way AddressLookup's city mode does; untested against the real lookup. If noisy, filter in the shared resolver.
- Use my location and the challenge page's Your place button were not exercised in the browser.
- A county pick applies the state and says so, which is honest but may surprise; revisit if county-grain stories arrive.

## Verdict

**approve-with-nits**
