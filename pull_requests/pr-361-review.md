---
pr: 361
branch: fix/360-oauth-control-plane-cors
title: "fix(api): close the OAuth token leak, gate the control plane, lock CORS"
author: sharankarthikyan (carried forward from #208)
reviewed_at: 2026-11-15
reviewer: coordinator (re-review of #208's Aug 12 request-changes review)
verdict: approve-with-nits
---

# PR Review: fix(api): close the OAuth token leak, gate the control plane, lock CORS

## Summary
Carries #208 forward (same commits and author) after merging `main`. The Aug 12 review found the three security fixes sound and bypass-resistant, but requested changes for four Important items. The author's later commits address each one, verified in the code below. Merging `main` needed two frontend resolutions. CI's starlette `TestClient` breaks on httpx 0.28, so the route-gating tests now use `httpx.ASGITransport`. The verdict is approve-with-nits, with one operational condition: production env vars must be set before deploying, or the admin panel returns 403.

## Scope of Change
- Files: `.env.example`, `api/app.py`, `api/auth.py`, `api/main.py`, `api/origins.py`, `api/routes/auth.py`, `api/routes/batch_jobs.py`, `api/routes/deployments.py`, three test files, `web_app/src/api/batchJobs.ts`, `web_app/src/api/deployments.ts`, `web_app/src/lib/authHeader.ts`
- Areas: api, web_app, tests

## CI Status
See the PR's checks (first CI run on this code: #208's fork runs never got workflow approval).

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. `.env.example` uses placeholders only (`you@example.com`).
- Fabricated data: n/a. Personal data: admin emails come from env, not code. Destructive data changes: none (an `is_admin` column already exists).

## Findings from the Aug 12 review — status
| # | Finding | Status (verified) |
|---|---|---|
| I-1 | HuggingFace `email_verified` key wrong | **Fixed:** `api/routes/auth.py:495` reads `emailVerified` or `email_verified`. |
| I-2 | Admin revocation waits for re-login | **Fixed:** `require_admin` checks `is_admin and is_admin_email(user.email)` at request time (`api/auth.py:191`). |
| I-3 | No test that routes are gated | **Fixed:** `tests/test_route_gating.py` asserts 401 anonymous, 403 non-admin, stale-flag rejection, the admin pass, and redirect drop/preserve. |
| I-4 | Deploy sequencing undocumented | **Fixed:** `.env.example` documents `ADMIN_EMAILS`, `CORS_ALLOWED_ORIGINS`, `BATCH_JOBS_ALLOW_LAUNCH`, `DEPLOYMENTS_ALLOW_LAUNCH`. |
| N-1 | Error-redirect paths unchecked | **Fixed** per commit `57d8f8b7` ("re-check error redirects"). |
| N-2–N-6 | Localhost dev origins in the prod default, type hints, reload fixture, comment, OTel | Not re-checked in detail; minor. |

## New in this PR
- Merge resolution keeps `main`'s `tracedFetch` and `authHeaders()` on every admin-gated call. Verified: no plain `fetch(` remains in either file, and launch/stop/log/deploy calls all pass `authHeaders(...)`.
- `TestClient` shim in `tests/test_route_gating.py`, with the same redirect-following default as starlette's client.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **Operational, before deploy:** set `ADMIN_EMAILS` in production. Optionally set `BATCH_JOBS_ALLOW_LAUNCH=1` / `DEPLOYMENTS_ALLOW_LAUNCH=1`, both now default off. Set `CORS_ALLOWED_ORIGINS` to the real front-end origins. Without these, admin routes return 403 and UI launches return 423.
### 🔵 Nits / suggestions (Minor)
- The Aug 12 nits N-2 to N-6 remain open as suggestions.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #360 (four parts), `Closes #360`, branch `fix/360-…` |
| Conventional Commits | ✅ | |
| No secrets | ✅ | |
| Tests | ✅ | 40 passed locally (gating, origins, account-link) |

## Test Coverage
- `pytest tests/test_route_gating.py tests/test_origins_security.py tests/test_oauth_account_link.py`: 40 passed.
- `cd web_app && npx tsc --noEmit`: clean.

## Verdict
**approve-with-nits.** Set the production env vars, then merge when CI is green.
