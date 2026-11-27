---
pr: 1269
branch: fix/1266-place-geojson-content-type
title: "fix(data-explorer): draw Cities & towns on the live site, where .geojson is served as octet-stream"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: eea1dc579ed1d038358721748e4b0d2e2c7ad069
verdict: approve
---

# PR Review: fix(data-explorer): draw Cities & towns on the live site, where .geojson is served as octet-stream

## Summary

Automated review (#648) for PR #1269 on `fix/1266-place-geojson-content-type`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/static_cache.py`
- `tests/test_static_cache.py`
- `web_app/src/pages/CensusDrilldownMapPage.tsx`
- `web_app/src/utils/fetchStaticJson.test.ts`
- `web_app/src/utils/fetchStaticJson.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `eea1dc579ed1`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**
