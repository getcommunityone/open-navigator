---
pr: 846
branch: feat/845-matrix-map-folio-look
title: "feat(web_app): give the Matrix map the look and motion of the Folio reference"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 89a96d5d539fde16b69624d950623e4a19a669ef
verdict: approve-with-nits
---

# PR Review: feat(web_app): give the Matrix map the look and motion of the Folio reference

## Summary

Restyles the Matrix map workspace to the Folio reference (paper and ink, Geist type, square controls, violet ramp,
KPI row, figure captions) and adds its motion (tile stagger and glide, growing bars, count-up numerals), all scoped
to one `.folio` wrapper and off under reduced motion. Routes, URL parameters and the scope label are unchanged. Unit
tests, type check and build pass; the layouts were rendered in a browser against a throwaway fixture, not the real
census bundle.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/package-lock.json`
- `web_app/package.json`
- `web_app/src/components/DotMatrixMap.tsx`
- `web_app/src/hooks/useCountUp.ts`
- `web_app/src/hooks/useFlip.ts`
- `web_app/src/hooks/usePrefersReducedMotion.ts`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/styles/folio.css`
- `web_app/src/utils/folioMotion.test.ts`
- `web_app/src/utils/folioMotion.ts`
- `web_app/src/utils/folioRamp.test.ts`
- `web_app/src/utils/folioRamp.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `89a96d5d539f`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. KPIs are computed from the loaded bundle; a missing value shows a dash and never counts up. The browser fixture was served by a request intercept and is not in the repo.

## Strengths

- Styles are scoped to `.folio`, so the rest of the app cannot be affected.
- The contrast rule for tile labels is a unit test over every ramp step, not a judgement call.
- The KPI row is hidden during a county drill-down, where state figures would contradict the scope label.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not seen against the real census bundle, and the dot map's shapes and county drill-down were not rendered (its
  map shapes come from a CDN the sandbox blocks). The owner should open each layout once after pulling.

### 🔵 Nit (Minor)

- `package-lock.json` loses several `libc` lines, a side effect of the npm version used. Harmless; CI installs from it.
- `.folio *` sets `border-radius: 0 !important`; round elements opt back in. Works, but is a blunt rule.
- Tiles re-flow without gliding on window resize.

## Verdict

**approve-with-nits**
