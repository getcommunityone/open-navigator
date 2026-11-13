---
pr: 231
branch: feat/139-explain-why-location
title: "feat(web_app): explain why the money modal asks for a location, ZIP is enough"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: coordinator (read the full diff against the rubric)
verdict: approve
---

# PR Review: explain why we ask for a location (#139)

## Summary

Validated issue #139 asks the site to collect only the location precision it needs. ZIP-only entry with no apartment
field already works on main (the gate defaults to a ZIP), so this PR changes only the copy. For each of the three
modes it explains that local taxes depend on where you live, so a ZIP, or a city or county, is enough. The promise
"Nothing stored" stays. The verdict is approve.

## Scope of Change

- Files changed: 1 (`web_app/src/components/MoneyGameModal.tsx`, +3 / -3)
- Areas touched: web_app (copy)

## CI Status

| Check | Status |
|---|---|
| Required checks | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data:** clean.
- **Personal data:** clean. The copy asks for less, and nothing is stored.
- **Destructive data changes:** clean.

## Findings

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | `Closes #139`; branch `feat/139-explain-why-location` |
| Conventional Commits | Pass | `feat(web_app)` |
| No fabricated data | Pass | |
| Tests | N/A | Copy only. `tsc` and the build pass |

## Verdict

Approve.
