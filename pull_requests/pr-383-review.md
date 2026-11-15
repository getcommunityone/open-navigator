---
pr: 383
branch: feat/248-application-links
title: "feat(dc): DC-1.3 admin-kept job-application links with verified-at and 30-day staleness"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: DC-1.3 application links (#383)

## Summary
Admins keep job-application links for data center projects on `/admin/application-links`. Each link records `last_verified_at` (a check that reached a live page, or an admin's Mark verified), and links not verified in 30 days are flagged on the admin screen and the public "Apply for jobs" section. It meets both lines of #248's "Done when". One security issue found in review (the server-side check could be pointed at internal addresses) was fixed on this branch before merge. Approve with nits.

## Scope of Change
- API: `api/routes/application_links.py` (public + admin routers), `api/models.py` (`JobApplicationLink`), router registration in `api/app.py` and `api/main.py`.
- Package: `ingestion.data_centers.application_links` (check, staleness, host guard) and the `verify_application_links` CLI; `httpx` added to `packages/ingestion` deps and `uv.lock`.
- Web: `ApplicationLinksAdminPage.tsx`, the admin tab and route, the Apply section on `DataCenters.tsx`, `applicationLinks.ts`, `verifiedLabel` (+ tests), `api.types.ts` (additions only).
- Docs: `data-center-application-links.md` (decisions recorded), a link from `data-center-jobs.md`.

## CI Status
Checked on the head commit before merge; see the PR's Checks tab.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: none.
- Fabricated data: none. Nothing is seeded; an empty table shows "No application links for <scope> yet", and a never-verified link reads "Not verified yet".
- Personal data: `created_by_user_id` only (FK, `ON DELETE SET NULL`).
- Destructive changes: a new table only; delete is admin-only and two-step in the UI.

## Strengths
- Writes are behind `require_admin` on the router, with a test for 401 (anonymous) and 403 (non-admin).
- Conservative "dead": only 404/410 hide a link, so a 403 bot filter or a timeout never removes a real posting.
- Changing a URL clears its verification, so a new link can't inherit an old "Verified" date.

## Findings
### 🔴 Blocking (Critical)
- **Fixed on this branch.** Server-side request forgery: "Check now" and the CLI requested any http(s) URL and followed redirects, so a link (or a redirect from one) could reach loopback, private networks or the cloud metadata address. `check_link` now follows redirects by hand, checks every hop with `host_is_public` (every resolved address must be global), and caps redirects at 5. Tests cover 127.0.0.1, 169.254.169.254, 10.0.0.5, localhost, a redirect to a private host, and a redirect loop.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The batch check isn't scheduled. Until it is, verification comes from "Check now" and "Mark verified". Scheduling is a deployment choice, so it stays out of this PR.
- DNS rebinding (an address that changes between the check and the request) isn't covered; acceptable for an admin-only action.
- `admin_list` loads every row and filters stale links in Python. Fine for a hand-kept list; page it if it grows past a few thousand.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first, four parts, Contract line before first commit | ✅ #248, Contract comment 2026-11-15 |
| Branch `<type>/<issue>-<slug>`, `Closes #248` | ✅ |
| Conventional Commits | ✅ |
| New Python in `packages/`, CLI as `python -m` | ✅ `ingestion.data_centers` |
| PK/FK on `public` tables | ✅ PK `job_application_link_id`, FK `created_by_user_id`; no FK to dbt relations, reason recorded |
| `state_code` and `state` both | ✅ |
| Loguru in the CLI, OpenTelemetry spans in the API | ✅ |
| No fabricated data | ✅ |
| Scope label rule | ✅ Apply section uses the page's `?state=&city=` scope and label |
| Decisions written down | ✅ `data-center-application-links.md` |

## Test Coverage
- API: 10 tests (`tests/test_api_application_links.py`), on in-memory SQLite.
- Package: 21 tests, including the host guard and redirects.
- Table created on PostgreSQL with its constraints; the CLI ran against it with a real page.
- Web: `verifiedLabel` tests; `tsc` and eslint clean.
- Not covered: the admin screen in a browser with a real admin login.

## Verdict
**approve-with-nits.**
