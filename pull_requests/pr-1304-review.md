---
pr: 1304
branch: feat/1301-mobile-location-header
title: "feat(web_app): phone header location selector, pin + ZIP with a one-tap National toggle"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 6b6fee81dd19d6dd8575960cb9397ef50204d76d
verdict: approve
---

# PR Review: feat(web_app): phone header location selector, pin + ZIP with a one-tap National toggle

## Summary

Automated review (#648) for PR #1304 on `feat/1301-mobile-location-header`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `pull_requests/assets/1301/before-home.png`
- `pull_requests/assets/1301/before-story.png`
- `pull_requests/assets/1301/phone-place-1-zip.png`
- `pull_requests/assets/1301/phone-place-2-town.png`
- `pull_requests/assets/1301/phone-place-3-home-national.png`
- `pull_requests/assets/1301/phone-place-4-story-town.png`
- `pull_requests/assets/1301/phone-place-5-other.png`
- `web_app/e2e/phone-place-header.check.mjs`
- `web_app/e2e/place-scope.check.mjs`
- `web_app/src/components/HeaderPlacePhone.test.tsx`
- `web_app/src/components/HeaderPlacePhone.tsx`
- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/utils/headerPlace.ts`
- `web_app/src/utils/headerPlacePhone.test.ts`
- `web_docs/docs/development/site-look-and-navigation.md`
- `web_docs/docs/guides/site-navigation.md`

## CI Status

See the PR checks on `6b6fee81dd19`.

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
