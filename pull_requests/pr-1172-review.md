---
pr: 1172
branch: fix/1170-topic-strip-duplicate-queries
title: "fix(home): topic strip runs one caption-facts query per distinct slug"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: coordinator (read-only pass; diff is 18 lines in one file)
verdict: approve
---

# PR Review: fix(home): topic strip runs one caption-facts query per distinct slug

## Summary
`HomeTopicStrip` built one `useQueries` entry per tile. Guide tiles have `facts: null`, so several entries shared the
key `['caption-facts', null, state, city]`, which made TanStack log `Duplicate Queries found` on every home render
(owner's console, #1170). The PR queries each distinct non-null slug once and maps results back to tiles by slug.
No behaviour change for captions. Verdict: approve.

## Scope of Change
- Files changed: 1 (`web_app/src/components/home/HomeTopicStrip.tsx`, +18 / -12)
- Areas touched: web_app
- Commits: fix(home): topic strip runs one caption-facts query per distinct slug (#1170)

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. Fabricated data: clean (no figures added). Personal data: none. Destructive changes: none.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits
None. Checked: tiles without a slug previously got a disabled query whose `data` was `undefined`; they now get
`undefined` directly, so `pickCaption(..., undefined, scope)` returns the same question/blurb fallback. Tiles that share
a slug now share one query's data, which is the intended result. The query key is unchanged, so the cache shared with
`HomeDataStories` (`caption-facts` for data-centers) still hits.

## Local checks
- `npx tsc --noEmit`: clean
- `npx vitest run src/utils src/components`: 461 passed (49 files)
- `npm run build`: clean
