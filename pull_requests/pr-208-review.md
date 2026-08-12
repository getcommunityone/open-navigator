---
pr: 208
branch: sharankarthikyan:feat/sharan-backend
title: "fix(api): close OAuth token leak, gate control-plane, lock CORS"
author: sharankarthikyan (Sharan Karthikeyan)
reviewed_at: 2026-08-12
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: request-changes
---

# PR Review: fix(api): close OAuth token leak, gate control-plane, lock CORS

## Summary
Closes three externally-reachable API holes — OAuth `redirect_uri` token exfiltration, an unauthenticated control-plane (batch-job launch/stop, prod deploys), and `allow_origins=["*"]` + credentials CORS — plus a follow-up requiring a verified email before OAuth account-linking. All three vulnerabilities are genuinely closed: the new origin validator survived an adversarial bypass battery, the admin gating is wired on every mutating route with matching frontend token plumbing, and the 11 new tests pass. Two small pre-merge fixes remain (a HuggingFace field-name mismatch that silently breaks legitimate account-linking, and missing route-gating tests), and no CI checks have run on the fork branch yet.

## Scope of Change
- Files changed: 12 (+457 / -44)
- Areas touched: api (auth, origins, routes), tests, web_app (API clients)
- Commits:
  - `fc36b070` fix(api): close OAuth token leak, gate control-plane, lock CORS ✅ conventional
  - `a186adc5` fix(api): require verified email before linking OAuth identity ✅ conventional
- Range reviewed: c995b10e..a186adc5

## CI Status
| Check | Status |
|---|---|
| Frontend Build | ⚠️ not run |
| Documentation Build | ⚠️ not run |
| Backend Tests | ⚠️ not run |
| API Types | ⚠️ not run |

No checks reported on the fork branch — workflows from `sharankarthikyan`'s fork are awaiting maintainer approval. All four required checks must run and pass before merge.

## Secrets Scan
**Clean — no secrets found in the diff.** All pattern hits are variable names, comments, `os.getenv()` reads, and the frontend reading its own bearer token from localStorage. No key material, no credentialed URLs.

## Strengths
- **The redirect validator is genuinely robust.** The reviewer ran a bypass battery against `api/origins.py` (`_normalize_origin` / `is_safe_redirect`): userinfo tricks (`https://allowed@evil.com`), subdomain suffixing (`allowed.com.evil.com`), query-smuggling, scheme/case games (`javascript:`, `HTTPS://`), backslash smuggling (`https:/\evil.com`, `/\evil.com`), protocol-relative `//evil.com`, and port confusion — all correctly rejected; default-port normalization and case-insensitive hosts correctly accepted. Parsing with `urlsplit().hostname` instead of string matching is the right primitive (api/origins.py:45-63, 103-116).
- **Defense-in-depth on the token append**: `redirect_uri` is validated at `/login` (api/routes/auth.py:220-222) *and* re-checked immediately before the JWT is appended (api/routes/auth.py:459-461), so even a stale/legacy `OAuthState` row can't leak the token.
- **Auth wiring is complete for everything mutating.** Deployments are gated at the router level so all routes inherit it (api/routes/deployments.py); batch-jobs `POST /launch`, `POST /launch/stop`, and `GET /launch/log` (log tail = potential secret leak) each carry `Depends(require_admin)`. The remaining open batch-jobs routes are read-only dashboards, and the SSE `/stream` payload is the sanitized summary, not log content — matching the PR's stated intent.
- **`require_admin` layering is correct**: 401 anonymous → 403 non-admin (api/auth.py:179-191); `is_admin` is re-stamped on every login including demotion, and the `is_admin` column + migration pre-existed at base — no missing-column landmine.
- **Frontend coverage is complete**: every plain-`fetch` caller of a gated endpoint now sends the token via `authHeaders()` (web_app/src/lib/authHeader.ts, batchJobs.ts, deployments.ts); the localStorage key matches `AuthContext.tsx`; the ungated status fetch correctly stays header-less.
- **Tests are real, not mocked** — `tests/test_oauth_account_link.py` exercises `get_or_create_user` against an actual SQLite session; `tests/test_origins_security.py` covers the key attack shapes. All 11 pass (verified by the reviewer via `.venv/bin/python -m pytest`).
- Facebook's synthetic placeholder email is correctly hard-pinned `email_verified=False` — the case where email-merge takeover was most plausible.
- Both app entrypoints (`api/main.py`, `api/app.py`) got the CORS fix; `BATCH_JOBS_ALLOW_LAUNCH` flipping to opt-in matches the deployments convention.

## Findings

### 🔴 Blocking (Critical)
None — no bypass of any of the three fixes was found.

### 🟡 Should fix (Important, non-blocking)
1. **HuggingFace `email_verified` key is wrong → HF users can never link to an existing account.** api/routes/auth.py:483 reads `data.get('email_verified')`, but the endpoint used is `whoami-v2` (api/auth.py:34), whose response is camelCase — the same block already reads camelCase `avatarUrl` (auth.py:486). The snake_case `email_verified` claim only exists on HF's OIDC `/oauth/userinfo`, which this code doesn't call. Result: always `False`, so any HF login matching an existing email 409s forever — and HF is a primary provider for this HF-Spaces-deployed app. It fails *closed* (security intact) but silently breaks a legitimate flow. Fix: `bool(data.get('emailVerified') or data.get('email_verified'))`, verified against a real whoami-v2 response.
2. **Admin revocation doesn't take effect until the demoted user logs in again.** `is_admin` is only re-stamped at login; `require_admin` trusts the persisted DB flag (api/auth.py:186). Removing an email from `ADMIN_EMAILS` leaves that user admin for the life of their 7-day JWT. For a control-plane gate, make the env authoritative at request time: `if not (user.is_admin and is_admin_email(user.email)): raise 403` — cheap, and turns `ADMIN_EMAILS` into a true kill switch.
3. **No test proves the routes are actually gated.** The vulnerability class here was *wiring* (`require_auth` existed before and was wired nowhere), but the new tests only cover `origins.py` and `get_or_create_user` in isolation — verified: neither test file contains a `TestClient` or touches the launch/deployments routes. Add a small `TestClient` test asserting `POST /api/batch-jobs/launch`, `POST /api/batch-jobs/launch/stop`, `GET /api/batch-jobs/launch/log`, and the deployments routes return 401 unauthenticated / 403 as non-admin, plus an end-to-end check that an unsafe `redirect_uri` to `/auth/login/{provider}` is dropped.
4. **Deploy-time sequencing needs documenting.** Existing admin rows have `is_admin=false` until the operator sets `ADMIN_EMAILS` *and* the admin re-logs-in; `BATCH_JOBS_ALLOW_LAUNCH` now defaults off. Both flips are intentional, but a fresh prod deploy without these env vars means the batch-jobs/deployments UI returns 401/403/423 with no runbook. Add `ADMIN_EMAILS`, `CORS_ALLOWED_ORIGINS`, and the launch flags to `.env.example`/deployment docs.

### 🔵 Nits / suggestions (Minor)
1. **Inconsistent defense-in-depth on the error-redirect paths.** The new failure handler re-checks `is_safe_redirect`, but four pre-existing error redirects (api/routes/auth.py:374, 386, 402, 409) use `oauth_state.redirect_uri` unchecked — verified. Safe today because `/login` validates before storage, but stale state rows spanning the deploy (10-min TTL) get an error-path open redirect, and it's a trap if another writer is ever added. Apply the same one-line re-check.
2. **Prod default allowlist includes localhost dev origins.** With `CORS_ALLOWED_ORIGINS` unset, production still trusts `http://localhost:5173` etc. with `allow_credentials=True` (api/origins.py:79). Low practical risk; consider gating dev defaults behind an env check.
3. `admin_emails() -> set` should be `set[str]` (api/auth.py:163); repo style mandates type hints.
4. The `test_origins_security.py` fixture's `importlib.reload` dance around the `lru_cache` is fragile; `allowed_origins.cache_clear()` in the fixture is simpler and less order-sensitive.
5. `is_safe_redirect` accepts any path/query on an allowlisted origin — fine, but a future open redirect on the *frontend* becomes a token-leak bounce. Worth a comment.
6. CLAUDE.md prescribes OpenTelemetry spans for FastAPI; the new security events (dropped redirect_uri, refused token redirect, 403s) are loguru-only. Consistent with the file's existing style, but these are exactly the events you'd want on a trace/alert path eventually.

## Project-Convention Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets/credentials in code | ✅ | scanned full diff — clean |
| No new code in scripts/ | ✅ | new Python is in api/ (correct home for API code) |
| No fabricated/placeholder data | ✅ | no served data touched |
| dbt for SQL transforms / medallion layering | n/a | no SQL transformations |
| PK/FK declared on public-schema models | n/a | no schema changes |
| Scope label matches active filter (frontend) | n/a | no scoped UI surfaces touched |
| Match evidence shown on filtered tiles | n/a | no filtered tiles touched |
| Conventional Commits | ✅ | both commits `fix(api): …` |
| Logging standard (loguru / OTel) | ⚠️ | loguru used in FastAPI paths (matches existing file style, but CLAUDE.md prescribes OTel — see nit 6) |

## Test Coverage
11 new tests, all passing (run by the reviewer subagent in `.venv`): `tests/test_origins_security.py` covers the origin/redirect validator against the main attack shapes (userinfo, subdomain-suffix, protocol-relative, backslash, scheme, port tricks); `tests/test_oauth_account_link.py` exercises `get_or_create_user` verified-email linking against a real SQLite session. **Gap:** nothing asserts the routes are actually gated (401/403) or that an unsafe `redirect_uri` is dropped end-to-end — the exact wiring failure this PR fixes (Important #3). CI has not run on the fork branch (awaiting workflow approval), so the required Backend Tests / API Types / Frontend Build / Documentation Build checks are unverified.

## Verdict
**Request changes** — the security fixes themselves are sound and bypass-resistant, but the HuggingFace `emailVerified` field mismatch silently breaks legitimate account-linking for the app's primary OAuth provider, there is no test guarding the route gating this PR exists to fix, and no required CI checks have run yet (fork workflows need approval). This matches the reviewer subagent's "Ready to merge: With fixes" assessment; both code fixes are small.
