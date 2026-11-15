---
pr: 375
branch: dependabot/uv/uv-fe6f02f2dc
title: "chore(deps): bump the uv group across 2 directories with 1 update"
author: dependabot[bot]
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: OpenTelemetry update (#375)

## Summary
Dependabot bumped only `opentelemetry-api` 1.42.0 → 1.45.2. `opentelemetry-sdk==1.42.0` requires `opentelemetry-api==1.42.0`, so pip's install failed (Backend Tests, API Types), the same failure as #364. Fixed on this branch by moving the whole OpenTelemetry family together in `requirements.txt`, `requirements-cpu.txt` and `apps/open-navigator-web/requirements.txt`:
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
