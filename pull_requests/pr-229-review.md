---
pr: 229
branch: feat/144-grandkids-takeaway-card
title: "feat(web_app): bold one-sentence takeaway above the grandkids forecast graph"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: coordinator (read the full diff against the rubric)
verdict: approve
---

# PR Review: bold takeaway above the grandkids forecast (#144)

## Summary

The PR adds the bold one-sentence takeaway that validated issue #144 asks for, above the grandkids forecast graph. The
sentence is built only from the two percentiles the graph already plots (local and U.S.), rounded the way the graph
labels them, so the sentence and the chart agree. It states the U.S. baseline when the place has no local cell. It
renders nothing while loading, on an error, or with no national value. No number is invented. The verdict is approve.

## Scope of Change

- Files changed: 1 (`web_app/src/components/MoneyGameModal.tsx`, +28 / -11)
- Areas touched: web_app
- Range reviewed: `origin/main...feat/144-grandkids-takeaway-card`

## CI Status

| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data:** clean. `takeaway` is `null` unless the real national percentile exists. The local figure is
  used only when `hasLocal` is true, and otherwise the sentence says there is no local data.
- **Personal data:** clean.
- **Destructive data changes:** clean.

## Findings

None blocking. 🔵 Nit: the old verdict line ("Better off" / "Tougher odds") becomes the plain title "Grandkids
forecast". The new card carries the comparison, with its numbers.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | `Closes #144`; branch `feat/144-grandkids-takeaway-card` |
| Conventional Commits | Pass | `feat(web_app)` |
| No fabricated data | Pass | Real plotted values only; no card without data |
| Tests | N/A | Presentation over existing values. `tsc` and the build pass locally and in CI. No screenshot, because the grandkids stage needs the live API |

## Verdict

Approve. Merge before #230, which is stacked on it.
