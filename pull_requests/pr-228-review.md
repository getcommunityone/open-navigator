---
pr: 228
branch: feat/149-prominent-trust-line
title: "feat(web_app): keep the trust line prominent above the money modal's address box"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: coordinator (read the full diff against the rubric)
verdict: approve
---

# PR Review: keep the trust line prominent (#149)

## Summary

The PR puts "Takes about 15 seconds · No data stored" right under the money modal's address box, at a readable size,
as validated feedback issue #149 asks. A clickable "No address? We'll use the median for <place>" appears only when the
site already has a real saved place. Without one, plain text points to the city or county links instead. Nothing is
invented. The verdict is approve.

## Scope of Change

- Files changed: 1 (`web_app/src/components/MoneyGameModal.tsx`, +41 / -2)
- Areas touched: web_app
- Range reviewed: `origin/main...feat/149-prominent-trust-line`

## CI Status

| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data:** clean. The median fallback uses only a real saved place (`knownPlace`), never a default area.
- **Personal data:** clean. Nothing new is stored, and the "No data stored" promise is unchanged.
- **Destructive data changes:** clean.

## Findings

None blocking. 🔵 Nit: `knownLabel || 'your area'` shows a generic label when a saved place has no name. That's
acceptable copy, and it isn't data.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | `Closes #149`; branch `feat/149-prominent-trust-line` |
| Conventional Commits | Pass | `feat(web_app)` |
| No fabricated data | Pass | The fallback appears only with a real place |
| Scope label / match evidence | N/A | |
| Tests | N/A | Copy and layout. `npx tsc --noEmit` and `npm run build` passed locally and in CI |

## Verdict

Approve.
