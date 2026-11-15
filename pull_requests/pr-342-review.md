---
pr: 342
branch: feat/260-web-request-tracing
title: "feat(web_app): trace every API request and link it to the API's trace"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: feat(web_app): trace every API request and link it to the API's trace

## Summary

Every request to the API now gets one `api.request` client span, opened in `lib/api.ts`. It carries a W3C
`traceparent` header, so the API's request span and its query spans join the browser's trace. The span keeps the
path and drops the query string, and only requests to our API get the span and the header. A new `tracedFetch` gives
code that calls `fetch` directly the same span, and the 24 direct API calls now use it. A table in the PR lists the
calls that stay, with the reason for each. Closes #260. Approve.

## Scope of Change

- Files changed: 17: `lib/api.ts` (span helpers, `tracedFetch`, `api` wired in), new `lib/api.test.ts`,
  `instrumentation.ts` (one comment), and 14 files where `fetch(` became `tracedFetch(` with its import
- Areas touched: web_app only. No API, dbt or package code.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. The `Authorization` header is set as before and never copied to a span.
- Fabricated data: none.
- Personal data: this is what the PR guards. Spans hold the method, the path and the status code. They never hold
  the query string, where the address search (`q`), the geocoder's typed address and the reverse geocoder's latitude
  and longitude travel. A failed request records only the error's type, since a message can quote the URL. A test
  checks that a typed address never reaches the span's attributes. Paths do carry IDs (`/{address_id}`,
  `/follow/user/{user_id}`), which the issue says to keep. None of them is free text.
- Destructive or bulky changes: none.

## Findings

None blocking, none to fix. Notes:

- **Same-origin `/api` counts as the API.** It's checked as well as `API_BASE_URL`, because the direct `fetch` callers
  hard-code `/api/...`. In development the Vite server proxies that path to the API, so it's still our API, and in
  production `API_BASE_URL` is `/api` anyway.
- **Behaviour is otherwise unchanged.** `tracedFetch` copies the caller's headers into a `Headers` object, which only
  lowercases their names. Requests to any other URL pass through untouched: no span, no header.
- **No parent span.** Request spans start under whatever context is active. With the default stack context manager,
  that's usually none, so a request span is a trace's root rather than a child of the route span. Linking it to the
  API's trace was this issue's goal. Nesting under route spans would need an async context manager, a new dependency
  the contract rules out.
- **Lint.** The changed files report the same problems before and after (all already there, such as
  `CensusDrilldownMapPage.tsx`'s `@ts-nocheck`). CI doesn't run lint.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #260 has all four parts; `Closes #260` |
| Conventional Commits | Yes | `feat(web_app): ...` with the co-author trailer |
| Tests | Yes | 6 new tests fail before and pass after; `npm test` 33 passed; `npx tsc --noEmit` and `npm run build` pass |
| React → OpenTelemetry (`CLAUDE.md`) | Yes | Uses the one tracer set up in `instrumentation.ts`, adds no SDK or exporter |
| No new dependency | Yes | `@opentelemetry/api` only, already in `package.json` |

## Verdict

Approve once the required checks are green.
