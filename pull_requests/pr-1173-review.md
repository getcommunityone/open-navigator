---
pr: 1173
branch: feat/1146-keyboard-a11y
title: "feat(a11y): keyboard navigation and screen-reader support, WCAG 2.2 AA (#1146)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 5b4b12da3d580b27b9898a970f8e6552c0390797
verdict: approve
---

# PR Review: feat(a11y): keyboard navigation and screen-reader support, WCAG 2.2 AA (#1146)

## Summary

Automated review (#648) for PR #1173 on `feat/1146-keyboard-a11y`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/a11y.e2e.ts`
- `web_app/package-lock.json`
- `web_app/package.json`
- `web_app/playwright.config.ts`
- `web_app/src/App.tsx`
- `web_app/src/components/Layout.tsx`
- `web_app/src/components/MoneyMovesTeaser.tsx`
- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/components/SkipLink.tsx`
- `web_app/src/components/StoryLenses.tsx`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/home/TopicCompaniesPanel.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/hooks/useMapKeyboard.tsx`
- `web_app/src/index.css`
- `web_app/src/lib/speakers.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/DecisionDetail.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/JurisdictionsSearch.tsx`
- `web_app/src/pages/OrganizationPage.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/pages/UnifiedSearch.tsx`
- `web_app/vite.config.ts`
- `web_docs/docs/development/accessibility.md`

## CI Status

See the PR checks on `5b4b12da3d58`.

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
