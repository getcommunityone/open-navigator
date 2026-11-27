---
pr: 1180
branch: fix/1179-find-your-town
title: "fix(web): drop the four hard-coded launch cities; home gets a Find your town prompt"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: coordinator (read-only pass over the diff and every caller)
verdict: approve
---

# PR Review: fix(web): drop the four hard-coded launch cities; home gets a Find your town prompt

## Summary
Removes the hard-coded launch-city list and launch-county map from the web app, replaces the home "Live in …" banner
with a Find your town button that opens the existing location picker, removes the picker's coverage gate and notices,
and removes Search's four-city county broaden. Verdict: approve.

## Scope of Change
- `HomeV9.tsx`, `AddressLookup.tsx`, `UnifiedSearch.tsx`; deleted `lib/launchCoverage.ts`, `lib/launchCounties.ts`;
  `web_docs/docs/guides/data-stories.md`. Merged main (conflict with #1173's banner recolour; kept the removal).

## Scans
- Secrets: clean. Fabricated data: clean — removes a hard-coded place list; the button shows only the reader's own
  saved place. Personal data: the saved location is already client-side; nothing new stored or logged. Destructive data
  changes: none (frontend only).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed on the branch.** Four leftover lines in `UnifiedSearch.tsx` still carried `?county=0` forward on navigation
  after the county toggle was removed; deleted.
- Behaviour change to note: picking a place with no meetings no longer warns up front; pages show their own empty
  states. That matches the No Fabricated Data rule (no stand-in data) and the owner's ask.

### 🔵 Nits
- Search's county broaden is gone for Tuscaloosa too until #1181 restores it from data.
- `JurisdictionsSearch` / `DataExplorerScorecardPage` use their own `?county=` (a county name) — unrelated, untouched.

## Local checks
- `npx tsc --noEmit`: clean; `npx vitest run src`: 63 files, 584 tests passed; `npm run build`: clean
