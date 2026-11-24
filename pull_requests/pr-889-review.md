---
pr: 889
branch: fix/888-admin-tabs-lighthouse-404
title: "fix(web_app): open Admin on Batch jobs and say plainly when a site has no Lighthouse audit"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 133de1dd0875270101c55fa3fe447fd462297642
verdict: approve-with-nits
---

# PR Review: fix(web_app): open Admin on Batch jobs and say plainly when a site has no Lighthouse audit

## Summary

Admin opened on the Lighthouse report, which shows a red error for any site with no stored audit, so the first thing an
operator saw was "HTTP 404". This PR puts Batch jobs first and Lighthouse last, sends `/admin` to `/admin/batch-jobs`,
and shows a neutral "No Lighthouse audit is stored for this URL" state on a 404. Read by the coordinator against the
diff; the heuristic scan ran first.

## Scope of Change

- `web_app/src/App.tsx`: `/admin` index redirects to `/admin/batch-jobs`.
- `web_app/src/components/AdminLayout.tsx`: tab order Batch jobs, Meeting kinds, Application links, Lighthouse report.
- `web_app/src/pages/LighthouseReportPage.tsx`: 404 is an empty state (`role="status"`); other errors stay red alerts.
- `web_app/src/utils/apiErrorMessage.ts` (+ test): reads `detail`, `message` or `error` from an error body; `ApiError`
  keeps the status.
- `web_app/src/pages/Settings.tsx`, `web_docs/docs/development/batch-load-tab.md`: copy matches the new order.

## CI Status

Required checks are read on the head commit before merge.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean.
- Fabricated data: none. The empty state shows the URL the operator submitted and no scores.
- Personal data, destructive changes: none.

## Strengths

- The 404 state says what is missing and what to try, and shows no stand-in numbers.
- The error-message helper is a pure function with its own tests, and now reads this API's `message` field, which the
  old inline code ignored (hence the bare "HTTP 404").

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- A 404 because the route itself is missing (an API started from older code) shows the same "no audit stored" text.
  The response body could tell the two apart; not worth holding this fix.
- Not checked against a running API here; the cloud session cannot reach the owner's.

## Verdict

**approve-with-nits**
