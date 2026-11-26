---
pr: 839
branch: fix/838-data-explorer-missing-bundle
title: "fix(web_app): say so when the Data explorer's census data files are missing"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve
---

# PR Review: fix(web_app): say so when the Data explorer's census data files are missing

## Summary
When the generated census bundle is absent, the Data explorer map drew a gray map and an empty metric list with no
explanation, because the missing manifest comes back as an HTML page with status 200. The PR detects that and shows an
explicit "No map data available" message with the command that creates the files, on both Map view and Matrix map.
Small, tested, and checked in a browser. Approve. It makes the failure visible; it does not restore the data.

## Scope of Change
- Files changed: 5 (excluding this review)
- Areas touched: web_app / web_docs
- Commits: `50cb334d` fix(web_app): say so when the Data explorer's census data files are missing
- Range reviewed: `origin/main...origin/fix/838-data-explorer-missing-bundle`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. This replaces a silent empty rendering with an explicit unavailable state, which is what the
"No Fabricated Data" rule asks for.

## Strengths
- The cause of the silence (HTML with status 200) is handled directly and has a test.
- Both tabs share one helper and one query key, so they cannot disagree about whether the bundle exists.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The manifest query on Map view now has `retry: false`, so the message appears at once instead of after a retry. A
  transient network failure will also show the message until reload; acceptable for a same-origin static file.
- `App.tsx`'s default redirect still fetches the manifest its own way and falls back to a hard-coded 2024 URL when it
  is missing. The map page then shows the new message, so the user is told; the redirect itself is unchanged.
- Only the manifest is checked this way. A bundle with a manifest but a missing year file still relies on the page's
  existing handling.
- The message names a developer command. That suits a local or admin reader; on the public site a plainer line may
  be wanted later.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #838 with the four parts; branch `fix/838-data-explorer-missing-bundle`; `Closes #838` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | Explicit unavailable state |
| Docs | Yes | `web_docs/docs/guides/data-explorer-matrix-map.md` |
| Tests | Yes | Four cases for the helper; the banner was checked in a browser, not by a component test |

## Test Coverage
`vitest run src/utils/fetchStaticJson.test.ts`: 4 passed. `npx tsc --noEmit` and `eslint` pass on the changed files.
In Chromium against the dev server with no bundle present, both tabs show the message and the command, with no page
errors.

## Verdict
approve.
