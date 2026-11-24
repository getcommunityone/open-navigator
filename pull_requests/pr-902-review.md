---
pr: 902
branch: fix/901-consistent-page-background
title: "fix(web_app): use one warm off-white page background on every page"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 4952e8fc2b7506f693433b657f540b3f75ac1ca3
verdict: approve
---

# PR Review: fix(web_app): use one warm off-white page background on every page

## Summary

Automated review (#648) for PR #902 on `fix/901-consistent-page-background`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/AdminLayout.tsx`
- `web_app/src/components/DataExplorerLayout.tsx`
- `web_app/src/components/Layout.tsx`
- `web_app/src/index.css`
- `web_app/src/pages/BillDetail.tsx`
- `web_app/src/pages/BrowseCauses.tsx`
- `web_app/src/pages/BrowseTopics.tsx`
- `web_app/src/pages/DataCenters.tsx`
- `web_app/src/pages/DataExplorerScorecardPage.tsx`
- `web_app/src/pages/DecisionDetail.tsx`
- `web_app/src/pages/EventBillDetail.tsx`
- `web_app/src/pages/Explore.tsx`
- `web_app/src/pages/GrantDetail.tsx`
- `web_app/src/pages/Home.tsx`
- `web_app/src/pages/JurisdictionsSearch.tsx`
- `web_app/src/pages/MeetingChat.tsx`
- `web_app/src/pages/MeetingCompare.tsx`
- `web_app/src/pages/MeetingDetail.tsx`
- `web_app/src/pages/MeetingDocuments.tsx`
- `web_app/src/pages/MoneyTalk.tsx`
- `web_app/src/pages/PersonDetail.tsx`
- `web_app/src/pages/PolicyMap.tsx`
- `web_app/src/pages/PolicyQuestionPage.tsx`
- `web_app/src/pages/PolicyQuestionsPage.tsx`
- `web_app/src/pages/UnifiedSearch.tsx`

## CI Status

See the PR checks on `4952e8fc2b75`.

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
