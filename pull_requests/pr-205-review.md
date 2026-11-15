---
pr: 205
branch: feature/pwa-and-geo-alerts
title: "feat(architecture): PWA scaffolding, PostGIS proximity routing, and generic asynchronous ingestion"
author: BlueHopper6
reviewed_at: 2026-11-15
reviewer: coordinator (v3 re-review after the author's Aug 22 and Nov 2 commits, plus a merge of current main)
verdict: approve-with-nits
review_version: 3 (supersedes the v2 request-changes review of 2026-08-12, posted on the PR)
---

# PR Review (v3): PWA scaffolding, proximity alerts, and generic asynchronous ingestion

## Summary
The v2 review found that the proximity scan could never return a result, that a hard-coded `gold.` schema guaranteed a 500 in production, and that the ingestion ended in a stub that fabricated a venue. The author's four later commits fix all three, along with nearly all the Important findings; each is verified in code below.

Since then I merged current `main` (conflicts resolved) and moved `vite-plugin-pwa` 0.17 → 2.0, which supports Vite 8 directly, so the peer-dependency override is dropped. I also fixed two things that broke after the merge: the PWA build failing on the 3 MB bundle, and the route tests' starlette `TestClient` (fails in CI on httpx 0.28).

One gap remains and is filed as #369: nothing in dbt reads the ingestion's Parquet files yet. Approve with nits.

## v2 findings — status (verified)
| v2 finding | Status | Evidence |
|---|---|---|
| 🔴 C1 empty data dependency | **Fixed** | Scan reads `event_place_geocoded` (`dbt_project/models/marts/event_place_geocoded.sql`, published to `public` by `publish_public_serving.sql`); every selected column exists in the model |
| 🔴 C2 hard-coded `gold.` | **Fixed** | Table name unqualified, resolved through the ORM search_path |
| 🔴 C3 load stub + fabricated venue | **Fixed** | `load_to_bronze` writes Parquet; `location_name` comes only from the source (`None` otherwise); `content_type` inferred by `Link` |
| 🟡 1 `packages.…` imports / `sys.path` hack | **Fixed** | `from models.proximity_alert import …`; no `sys.path` |
| 🟡 2 dropped city prop / `as any` / `@ts-ignore` | **Fixed via main** | `main`'s versions of the three files kept |
| 🟡 3 unclamped `acos`, commit before scan | **Fixed** | `LEAST(1.0, GREATEST(-1.0, …))`; `flush()` then commit after the scan |
| 🟡 4 migration deleted | **Fixed** | `packages/hosting/scripts/neon/migrations/111_create_proximity_alerts.sql` restored |
| 🟡 5 zero tests | **Fixed** | `tests/test_proximity_alerts.py` (schema bounds, route auth, scan, ingestion transform/load, retry) |
| 🟡 6 PWA not installable | **Fixed** | 192 and 512 px icons in `web_app/public/` and the manifest |
| 🟡 7 stale description / README | **Moot** | The README conflict resolved to `main`'s README; the PR's README curl example is gone |
| 🔴 B4 inert PostGIS compose image | **Fixed** | `docker-compose.yml` uses `postgres:16` |
| 🔵 vite-plugin-pwa 0.17 forced onto Vite 8 | **Fixed** here | Upgraded to 2.0; override removed |

## Changes made in this re-review
- Merged current `main` (alerts router mounted alongside feed and data-centers; datamodels deps combined; `main`'s README and TypeScript fixes kept).
- `web_app/vite.config.ts`: `maximumFileSizeToCacheInBytes: 5 MB`, since PWA 2.x fails the build on the ~3 MB main bundle.
- `tests/test_proximity_alerts.py`: `TestClient` replaced with an `httpx.ASGITransport` client.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- Ingestion Parquet isn't read by dbt yet, while the docstring says it is: #369.
### 🔵 Nits / suggestions (Minor)
- No frontend calls `POST /api/alerts/proximity` yet; it's a backend-only feature until a UI uses it.
- The service worker precaches the whole ~3 MB app. `registerType: 'autoUpdate'` keeps it current, and `/api` and `/docs` are excluded from the navigation fallback.
- Three pre-existing ruff findings in `tests/test_proximity_alerts.py` (import order, alias, `datetime.UTC`).

## Test Coverage
- `tests/test_proximity_alerts.py` plus route-gating, feed, geocode, OAuth, origins, ORM-pooler and datamodels suites: 100 passed after merging current `main`.
- `cd web_app && npx tsc --noEmit`: clean. `npx vite build`: passes and generates `sw.js` and the manifest.

## Verdict
**approve-with-nits.** Merge when CI is green.
