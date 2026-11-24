---
pr: 902
branch: fix/901-consistent-page-background
title: "fix(web_app): use one warm off-white page background on every page"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 4952e8fc2b7506f693433b657f540b3f75ac1ca3
verdict: approve-with-nits
---

# PR Review: fix(web_app): use one warm off-white page background on every page

## Summary

Every full-page shell now uses one class, `page-bg` (#fafaf9), matching the home page sections, in place of slate-300, slate-200, gray-50 and a mint tint. A class swap with no behaviour change.

Read by the coordinator against the diff and screenshots; the heuristic scan ran first.

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

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- Detail pages (decision, meeting, bill, person, grant) got the same swap but were not screenshotted; they need real records.
- Contrast was not measured; the text is the same dark slate on a lighter background than before.
- The 404 page keeps its gradient and Data Stories keeps its paper colour, so two page colours remain by design.

## Verdict

**approve-with-nits**
