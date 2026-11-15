---
pr: 364
branch: dependabot/uv/uv-19228c887b
title: "chore(deps): bump the uv group across 2 directories with 12 updates"
author: dependabot[bot]
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: dependency update (#364)

## Summary
Python (uv group, 12 updates). Notable: `mlflow` 3.2 → 3.17, `filelock` 3 → 4 (major), `Pillow` 12 → 13 (major), `langgraph` floor to 1.2.14 in `requirements-cpu.txt`, `setuptools` 81 → 84, `pypdf` 6.21.4. It failed CI because `opentelemetry-api` was bumped to 1.45.2 while `opentelemetry-sdk==1.42.0` requires 1.42.0; fixed on this branch by keeping the api at 1.42.0 in the three requirement files.

## Scans
Secrets, fabricated data, personal data, destructive data changes: none (manifests and lockfiles only).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `mlflow` and `langgraph` back the agents package (MLflow tracing, LangGraph); Backend Tests pass. `filelock` and `Pillow` majors are transitive or OCR-only. The OpenTelemetry family should be bumped together in a later update.

## CI Status
Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions: success on the updated head.

## Verdict
**approve.**
