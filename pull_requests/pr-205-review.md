---
pr: 205
branch: feature/pwa-and-geo-alerts
title: "feat(architecture): PWA scaffolding, PostGIS proximity routing, and generic asynchronous ingestion"
author: BlueHopper6
reviewed_at: 2026-07-29
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: request-changes
---

# PR Review: PWA scaffolding, PostGIS proximity routing, and generic asynchronous ingestion

## Summary
Adds vite-plugin-pwa to the web build, a PostGIS-backed `POST /api/alerts/proximity`
endpoint with a new `proximity_alerts` ORM table + migration, and a "generic municipal
ingestion" script. The auth, SQL-parameterization, and Pydantic-validation work is
genuinely solid, but the headline proximity feature was verified non-functional against
the real database at four independent layers, the ORM change regresses `init_db()` on
every current runtime target, and the ingestion script violates the frozen-`scripts/`
rule and doesn't actually load anything. Request changes.

## Scope of Change
- Files changed: 17 (+7,806 / −2,463; ~9,900 lines of that is `package-lock.json` churn)
- Areas touched: api (routes/models/main), packages/datamodels, packages/hosting
  (migration), scripts (new file — violation), web_app (PWA config, deps, tsx fixes),
  Dockerfile, docker-compose, requirements.txt
- Commits (all Conventional-Commit conformant):
  - `12ceff64` feat(architecture): scaffold PWA configuration and PostGIS geospatial models
  - `ce918e24` feat(api): integrate PostGIS proximity routes, containerize geo-dependencies, and hydrate frontend lookup components
  - `ede3a012` feat(ingestion): scaffold generic asynchronous ETL pipeline with CLI parameterization
  - `bffc108c` build(web_app): override vite-plugin-pwa peer dependency to resolve CI/CD conflicts
  - `402513ba` chore(web_app): sync package-lock.json for Vite override
  - `c7c4aaca` chore(web_app): explicitly add emnapi dependencies to resolve cross-platform CI lockfile mismatches
- Range reviewed: `59147bdb..033b7cae` (review tooling paths excluded)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | ✅ |
| Documentation Build | ✅ |
| Backend Tests | ✅ |
| API Types | ✅ |

(Docker Build Test triggered by the Dockerfile/compose changes and was still running at
review time; it is not a required check.)

## Secrets Scan
**Clean** — no API keys, tokens, passwords, private keys, or credentialed connection
strings found in the diff (including a pattern skim of the `package-lock.json` churn).

## Strengths
- Auth is genuinely enforced: `api/routes/alerts.py:16` uses `Depends(require_auth)`,
  which raises 401 on missing/invalid credentials.
- No SQL injection: the raw `ST_DWithin` query uses `sqlalchemy.text()` with bound
  parameters; the WKT point is built from Pydantic-validated floats.
- Tight Pydantic validation: `packages/datamodels/models/proximity_alert.py:6-9` bounds
  radius (100 m–50 km), latitude (±90), longitude (±180).
- The migration (`packages/hosting/scripts/neon/migrations/111_create_proximity_alerts.sql`)
  declares an explicit PK, FK to `"user"` with `ON DELETE CASCADE`, and the promised
  GiST index; numbering is correct.
- Fixes a real pre-existing bug: missing line continuation in `Dockerfile:23`.
- `AddressLookup.tsx:213` `window.setTimeout` is the correct fix for the
  browser-vs-Node timer typing conflict from the `@types/node` bump.
- Lockfile churn skimmed: no suspicious dependency additions (workbox 7.4.1,
  `@types/node` 26, `@emnapi` pins — all plausible).

## Findings

### 🔴 Blocking (Critical)
1. **New file under frozen `scripts/`** —
   `scripts/datasources/municipal_generic/ingest_agendas.py` (199 lines). CLAUDE.md:
   `scripts/` is frozen; new runnable Python must be a package CLI module
   (`python -m <lib>.<module>`). Also breaks the `load_` prefix convention for
   `scripts/datasources/`. Fix: move to `packages/ingestion/src/ingestion/…`.
2. **The proximity endpoint cannot work against the real database** (verified live on
   `localhost:5433/open_navigator`): (a) PostGIS is neither installed nor installable on
   the native cluster (no OS package); (b) `civic_organization` exists only in `gold`,
   not `public`, and the ORM engine's search_path is public-first
   (`api/database.py:59,78`); (c) the query selects `org_id`/`org_name` but the table's
   columns are `id`/`name` (`api/routes/alerts.py:38-53`); (d) `latitude`/`longitude`
   are NULL on all 43,726 rows, so even fully fixed it returns nothing. The endpoint was
   never run. Fix: provision PostGIS deliberately (or use a haversine expression needing
   no extension), publish a geo-populated relation to `public` via dbt, correct the
   column names — or pull the endpoint from this PR.
3. **`ProximityAlert` ORM model breaks `init_db()` on every current runtime target**
   (`api/models.py:210-222`): `Base.metadata.create_all` at startup fails on the real
   cluster (no PostGIS) and on the SQLite fallback (no SpatiaLite); the startup
   `try/except` in `api/main.py:436-442` swallows it, so the route 500s at
   `db.commit()`, and on a fresh DB a mid-`create_all` abort can leave other auth/ORM
   tables uncreated. Neither the model path nor migration 111 issues
   `CREATE EXTENSION IF NOT EXISTS postgis`.
4. **`docker-compose.yml:26` PostGIS image swap is inert** — the live warehouse is the
   native cluster on 5433, not the compose service. The change provisions nothing while
   looking like it provisions PostGIS, which is exactly how findings 2–3 shipped.

### 🟡 Should fix (Important, non-blocking)
1. **Service-worker navigation fallback will hijack non-SPA routes** —
   `web_app/vite.config.ts:10-28` uses generateSW defaults with no
   `navigateFallbackDenylist`, so installed clients get the SPA shell for `/api/docs`
   and `/docs/`. Add `workbox: { navigateFallbackDenylist: [/^\/api/, /^\/docs/] }`.
   Also `devOptions.enabled: true` registers the SW against the dev server (stale-content
   trap), and the manifest ships only a 64×64 icon — Chrome needs 192/512 px, so the PWA
   isn't actually installable.
2. **Type errors silenced instead of fixed** — `HomeV9.tsx:1384` (`as any`),
   `main.tsx:30` (`@ts-ignore`), and worst, `PolicyQuestionsPage.tsx:287`
   (`{...({ city: scopedCity } as any)}`): `QuestionMeetingList` declares no `city`
   prop, so the city scope is silently dropped for that list — a latent scope-label-rule
   violation the cast hides from the compiler. Wire the prop instead.
3. **Async route blocks the event loop** — `api/routes/alerts.py:14` is `async def` but
   uses the synchronous SQLAlchemy Session over an unindexable per-row-cast scan; make it
   sync `def` (threadpool) and add `ORDER BY` distance before `LIMIT 100`.
4. **Zero tests** for the route, model, schemas, or ingestion script — backend CI passed
   because nothing exercises the new code.
5. **Fragile import path** — `from packages.datamodels.models…`
   (`alerts.py:9`, `ingest_agendas.py:19` + `sys.path` hack) only resolves from repo
   root; the installed import name is `models` (see `packages/datamodels/pyproject.toml`).
6. **The ingestion "pipeline" doesn't ingest** — the Load step is a log line + "Insert
   loading logic here" (`ingest_agendas.py:180-183`) against a fictional endpoint shape;
   it fabricates `"{municipality} City Hall"` locations (`:143`) and stamps every video
   `content_type="video/mp4"` (`:169`) — dead code today, but against the
   no-fabricated-data rule the moment the loader is wired; the tenacity predicate also
   retries hard 404s five times.
7. **PR description inaccuracies** — no frontend code calls the new endpoint (the
   "hydrated components" change is a one-line typing fix), and the migration lives under
   `packages/hosting/scripts/neon/migrations/`, not `packages/datamodels/migrations/`
   (and the Neon target never enables PostGIS either).

### 🔵 Nits / suggestions (Minor)
1. `api/routes/alerts.py`: unused imports; `ProximityAlertResponse`/`Update` defined but
   unused — an alert you can create but never view, edit, or receive.
2. `api/models.py:218-219`: deprecated `datetime.utcnow` (consistent with existing
   models, so cosmetic).
3. `packages/datamodels/pyproject.toml`: pydantic used but not declared as a dependency.
4. `ingest_agendas.py:25`: stdlib `logging` instead of loguru; no OTel span in the new
   route (the API has no `FastAPIInstrumentor` at all — pre-existing gap).
5. `Dockerfile:50` `npm ci --legacy-peer-deps` diverges from CI's plain `npm ci`;
   better long-term fix is upgrading `vite-plugin-pwa` (0.17.5, peer-pinned Vite 3–5,
   force-overridden to Vite 8) rather than the `overrides` hack.

## Project-Convention Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets/credentials in code | ✅ | diff + lockfile scanned, clean |
| No new code in scripts/ | ❌ | new `ingest_agendas.py` under scripts/datasources/ |
| No fabricated/placeholder data | ⚠️ | nothing reaches a served path, but the (dead) pipeline fabricates locations/content types |
| dbt for SQL transforms / medallion layering | ⚠️ | runtime ORM table follows the auth-table exception ✓, but route reads a warehouse table not published to `public` |
| PK/FK declared on public-schema models | ✅ | migration 111 declares PK + FK + indexes |
| Scope label matches active filter (frontend) | ⚠️ | `as any` cast hides a dropped `city` prop in PolicyQuestionsPage |
| Match evidence shown on filtered tiles | n/a | no filtered result surfaces touched |
| Conventional Commits | ✅ | all 6 commits conform |
| Logging standard (loguru / OTel) | ❌ | stdlib logging in the script; no OTel in the new route |

## Test Coverage
None added. No tests for the proximity route, the ORM model, the Pydantic schemas, or
the ingestion script. Backend Tests CI is green only because nothing imports or
exercises the new code paths.

## Verdict
**Request changes.** The reviewer subagent's assessment was "Ready to merge? No," and
coordinator spot-checks (live DB column/table verification, vite config, scripts/ file)
confirmed the load-bearing findings. The salvageable pieces — the Dockerfile fix, the
timer typing fix, and the PWA plumbing minus the SW-fallback footgun — are a small
fraction of the PR; the core feature needs a real PostGIS/provisioning decision, a
`public`-published geo source, and tests before it can land.
