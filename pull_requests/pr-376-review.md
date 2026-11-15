---
pr: 376
branch: dependabot/uv/uv-e3157454d1
title: "chore(deps): bump the uv group across 2 directories with 8 updates"
author: dependabot[bot]
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: OpenTelemetry update (#376)

## Summary
Among 8 updates (aiohttp, fsspec, mako, mlflow 3.17.2, multidict, urllib3, werkzeug patch/minor bumps), Dependabot bumped `opentelemetry-api` 1.42.0 → 1.45.2 alone. `opentelemetry-sdk==1.42.0` requires `opentelemetry-api==1.42.0`, so pip's install failed (Backend Tests, API Types), the same failure as #364. Fixed on this branch by moving the whole OpenTelemetry family together in `requirements.txt`, `requirements-cpu.txt` and `apps/open-navigator-web/requirements.txt`:
- `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http` 1.42.0 → 1.45.2;
- `opentelemetry-instrumentation-fastapi`, `-asyncpg`, `-psycopg2`, `-sqlalchemy` 0.63b0 → 0.66b2.

`uv pip compile` resolves both `requirements.txt` and the web app's requirements with these pins.

## Scans
Secrets, fabricated data, personal data, destructive changes: none (manifests and lockfile only).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Dependabot groups OpenTelemetry packages separately, so this will recur. A Dependabot group that bumps `opentelemetry-*` together would stop it.

## Verdict
**approve** once CI is green.
