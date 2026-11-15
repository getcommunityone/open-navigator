---
pr: 230
branch: feat/138-condense-grandkids-forecast
title: "feat(web_app): condense the grandkids forecast section"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (coordinator)
verdict: approve-with-nits
---

# PR Review: feat(web_app): condense the grandkids forecast section

## Summary

Issue #138 said the grandkids forecast section in the money modal was too long. This PR condenses it: only the Parent
income selector shows by default, Child race and Child gender move under a "More filters" disclosure (open when either
is already set), and the caveat note and source fold into one "About this data" disclosure. The separate "no local
data" paragraph goes, because the takeaway card from #229 (merged) already says that case in its sentence. No data,
API or number changes. It was stacked on #229, and after syncing `main` the diff is only the condensing change in
`MoneyGameModal.tsx`. It type-checks and builds. The verdict is approve, with three nits.

## Scope of Change

- Files changed: 1 after the sync (`web_app/src/components/MoneyGameModal.tsx`, +29 / -25)
- Areas touched: web_app
- Commits: 648ae65 feat(web_app): condense the grandkids forecast section; a merge of `main`
- Range reviewed: `main` at the sync to the merge commit

## CI Status

Checked green on the final head before merging (Frontend Build, Documentation Build, Backend Tests, API Types).
Locally: `tsc --noEmit` passes on the synced branch, and `main` plus #228, #229, #230, #231 and #232 together
type-check and build.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. Nothing new is shown. Every figure is still the real API value, and the
  no-local-data case is still stated, in the takeaway sentence.
- **Personal data:** clean.
- **Destructive data changes:** none.

## Strengths

- Keeps the insight and drops the text, which is what #138 asked for, without retiring the API.
- The disclosure opens by itself when a non-default filter is already active, so a chosen filter is never hidden.
- The source and caveat stay on the page, one click away.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **"More filters" can close under the user's hand.** `open` is passed as a prop, and React writes it only when the
   value changes. If someone opens the panel, picks a race, then sets it back to the default while gender is also the
   default, the prop flips from true to false and the panel closes. Holding `open` in state (set from the filters on
   first render, updated in `onToggle`) would fix it.
2. **The source is now hidden by default.** The takeaway makes a numeric claim, so a short visible "Source: Opportunity
   Atlas" line under it would keep the attribution in view, with the full note still in the disclosure.
3. **"Your area" in the no-data sentence.** When no place matched, the takeaway from #229 reads "(no local data for Your
   area in this group)". Saying "no local data for this place" in that case reads better.

## Repo-Rule Compliance

| Rule (CLAUDE.md) | Status |
|---|---|
| No Fabricated Data | ✅ |
| Conventional Commits | ✅ |
| Never push to `main`, never force-push | ✅ |
| Required checks green | re-checked on the final head |
| Issue first, `Closes #<issue>` (AGENTS.md) | ✅ `Closes #138`; branch `feat/138-...` |

## Test Coverage

The web app has no unit test runner. The change is covered by `tsc --noEmit` and the build. No screenshot: the section
needs `/api/grandkid-outlook` and a resolved place.

## Verdict

**Approve with nits.** Merge when the four required checks are green. The nits can be one follow-up issue.
