---
pr: 363
branch: fix/362-money-modal-polish
title: "fix(money): animate the estimate sliders and point a blocked reveal at the next slider"
author: 3ni8ma (carried forward from #210)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: fix(money): animate the estimate sliders and point a blocked reveal at the next slider

## Summary
Carries #210's money-modal polish forward after merging `main`.
- **Animation:** staggered slider sweep and fade-up; Reveal pulses from the start.
- **Blocked reveal:** a click before every guess is made focuses the first unguessed slider (`aria-disabled` kept).
- **Copy:** friendlier address placeholder.

Conflicts resolved:
- **Income row:** keeps `main`'s ACS-seeded income slider (#354), with this PR's sweep delay added.
- **Grandkids verdict:** `main`'s numeric mobility takeaway replaces this PR's version, since `main` had already made it a concrete number from the plotted percentiles.

## Scope of Change
`web_app/src/components/MoneyGameModal.tsx` (+~23/-14 net vs main), `web_app/src/index.css` (+10/-1).

## Scans
Secrets, fabricated data, personal data, destructive changes: clean. No figures are added. The animation only changes how existing real values appear.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Dropping native `disabled` on Reveal in favour of `aria-disabled` is deliberate, so a blocked click can move focus; the click handler guards it. Keyboard users get the same focus jump.

## Test Coverage
- `npx tsc --noEmit` and ESLint on `MoneyGameModal.tsx`: clean after the merge.
- Rendered in headless Chrome against a mock API (test values, not committed): the estimate sliders finish their sweep fully visible, and the income row shows "Household income · local median $52,000".
- No automated UI tests exist for the modal.

## Repo-Rule Compliance
Issue #362 (four parts), `Closes #362`, branch `fix/362-…`, Conventional Commits, reduced-motion respected.

## Verdict
**approve.** Merge when CI is green.
