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

## Addendum: pyarrow needs NumPy 2 (2026-11-15)
After the OpenTelemetry fix the install succeeded, but tests failed with `pyarrow requires NumPy 2.0 or newer, found 1.26.4`. This update raises `pyarrow` 14.0.2 → 26.0.1. That's a security fix: CVE-2026-25087 / GHSA-rgxp-2hwp-jwgg (use-after-free, fixed in 23.0.1), and 26.0.1 also patches the bundled Brotli. So it is kept, and the pins capping NumPy below 2 move up instead:
- `requirements.txt`: `pandas` 2.1.4 → 2.2.3, `spacy` 3.7.2 → 3.8.7, `matplotlib` 3.8.2 → 3.11.2 (each of the old versions required `numpy<2`);
- `apps/open-navigator-web/requirements.txt`: `pandas` 2.1.4 → 2.2.3.

`uv pip compile` resolves `requirements.txt`, `requirements-cpu.txt` and the web app's requirements to `numpy` 2.4.6 with `pyarrow` 26.0.1.

Locally, with `numpy` 2.4.6 / `pandas` 2.2.3 / `pyarrow` 26.0.1:
- the 8 tests that failed in CI pass (38 in those files);
- the `packages/ingestion`, `packages/llm` and `packages/datamodels` suites plus the API route tests: 857 passed. The only failures are the 2 `test_meeting_gap_analysis` tests that fail on `main`, and 22 errors from `pytest-httpx` missing in the local environment (CI installs it).

No spaCy language model is pinned to 3.7 in the repo. The `scrapers[ocr]` extra still caps `numpy<2`, but it isn't installed in CI or the API image.
