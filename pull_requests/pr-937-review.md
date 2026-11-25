---
pr: 937
branch: fix/936-stale-deploy-reload
title: "fix(web_app): reload once when a deploy removed a lazy page's chunk, and stop telling visitors to run npm install"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: frontend-specialist subagent (read-only) and coordinator
head_sha: 4e13074f
verdict: approve
---

# PR Review: fix(web_app): reload once when a deploy removed a lazy page's chunk, and stop telling visitors to run npm install

## Summary

A tab open across a deploy asks for hashed lazy chunks the deploy removed. On production, `assets/ScrollCue-C-uJ7YO1.css` is
a 404 after #931. The Data Story then showed "could not be loaded … run npm install". This PR reloads the page once on
Vite's `vite:preloadError`, shows "Loading the latest version of …" while it does, and stops after one reload per missing
file (or within 30s, or offline). In production, the visitor-facing message says the site was updated (or that the
visitor is offline) instead of giving developer advice.

The first review pass found one important issue (cancelling the event replaced the real error with a React.lazy TypeError
during the reload) and three minor ones. All four are fixed in `3b3dc033` and verified in a real browser. Verdict:
**approve**.

## Scope of Change

- Files changed: 7 (web_app 6, web_docs 1), plus this review
- Areas touched: web_app, web_docs
- Commits:
  - 3e6263d3 fix(web_app): reload once when a deploy removed a lazy page's chunk, and stop telling visitors to run npm install
  - 965b7a0d docs(pr-937): auto-write rubric review [skip review] (CI bot)
  - 3b3dc033 fix(web_app): let the failed import keep its real error, guard the reload per file, and skip it offline
- Range reviewed: `8fa69852..4e13074f`

## CI Status

| Check | Status |
|---|---|
| PR conventions | see PR checks on the head |
| Frontend Build / Documentation Build / Backend Tests / API Types | see PR checks; locally `vitest` 376/376, `tsc` clean, `vite build` OK |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data in a served path: clean. Only messages and reload logic; no figures.
- Personal data: clean. sessionStorage holds only the failing chunk's error text and a timestamp, per tab.
- Destructive or bulky changes: none.

## Strengths

- The real error always reaches the boundary, and the reload is a recovery layered on top, so nothing is hidden when it
  doesn't work.
- Every exit is fail-closed: no storage, offline, the same file twice, or within 30s, all mean no reload, so the page can't
  loop.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

1. `staleDeploy.ts`: `event.preventDefault()` on `vite:preloadError` made Vite's `handlePreloadError` return normally, so
   `import()` resolved to `undefined`. React 18 `lazy` then threw `Cannot read properties of undefined (reading 'default')`,
   which the boundary showed until the reload landed. Verified in `node_modules/vite/dist/node/chunks/node.js:27046-27051`.
   **Fixed:** the event is no longer cancelled; a module-level pending flag drives a "Loading the latest version of …"
   status in `LazyRouteBoundary`. A unit test asserts `defaultPrevented === false`. In the browser, the "recover" scenario
   recorded **no** alert at any point (an observer that survives reloads).

### 🔵 Nits / suggestions (Minor)

2. Docs and header said only "index.html is no-cache"; the PWA service worker also serves navigations. **Fixed:** both
   explain it and link `deployment/huggingface-spaces.md`.
3. The guard was time-only: a load slower than 30s on a lazy deep link could loop, and a clock stepping back blocked
   reloads. **Fixed:** it never reloads twice for the same failing message, and a future timestamp counts as expired.
   Unit-tested.
4. A network failure has the same wording as a missing chunk. **Fixed:** no reload when `navigator.onLine === false`, and
   the message says offline. Unit-tested.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/936-…`; `Closes #936`; issue has all four parts |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | n/a | No scope change; the Data Story's own scope label is unaffected |
| Match evidence on filtered tiles | n/a | |
| Docs | ✅ | `web_docs/docs/guides/data-explorer-matrix-map.md` |
| Telemetry and logging | n/a | |
| Tests | ✅ | 9 new unit tests; the production-hint tests fail on `main`'s helper |
| Shared libraries | n/a | |

## Test Coverage

- `npx vitest run`: 38 files, 376 tests pass. `npx tsc --noEmit`: clean. `eslint` on the changed files: clean.
- Production build served with `vite preview`, in Chromium with the service worker blocked:
  - **recover** (first `DataStory-*.js` request 404s): 1 reload, the Data Story renders, no alert ever shown.
  - **missing** (always 404): 1 reload, then a single alert with the real error ("Failed to fetch dynamically imported
    module …"), and no further reloads.
- Not covered by an automated test: `componentDidCatch` itself (covered by the browser runs), and a tab controlled by an
  old service worker (documented).

## Verdict

**approve**: merge once the required CI checks are green on the head.
