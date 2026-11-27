---
pr: 1197
branch: fix/1191-site-navigation
title: "fix(web): site navigation \u2014 phone menu, header place control, Places link, per-page titles"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 57e7b1e45d7963248b11f785d42d25be10be77bc
verdict: approve
---

# PR Review: fix(web): site navigation — phone menu, header place control, Places link, per-page titles

## Summary

Automated review (#648) for PR #1197 on `fix/1191-site-navigation`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/App.tsx`
- `web_app/src/components/Layout.tsx`
- `web_app/src/components/LocationPickerDialog.tsx`
- `web_app/src/components/SiteFooter.tsx`
- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/hooks/usePlacePick.ts`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/JurisdictionsSearch.tsx`
- `web_app/src/pages/MeetingDocuments.tsx`
- `web_app/src/pages/UnifiedSearch.tsx`
- `web_app/src/utils/headerPlace.test.ts`
- `web_app/src/utils/headerPlace.ts`
- `web_app/src/utils/navActive.test.ts`
- `web_app/src/utils/navActive.ts`
- `web_app/src/utils/useDocumentTitle.test.ts`
- `web_app/src/utils/useDocumentTitle.ts`
- `web_docs/docs/development/site-look-and-navigation.md`
- `web_docs/docs/guides/site-navigation.md`

## CI Status

See the PR checks on `57e7b1e45d79`.

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
