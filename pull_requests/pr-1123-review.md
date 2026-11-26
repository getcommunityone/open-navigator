---
pr: 1123
branch: feat/1122-home-hero-points
title: "feat(home): hero shows three numbered points from the record, with story buttons (#1122)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: e60758e05bb3b03c58a1b344f3af83e74c20dd2a
verdict: approve
---

# PR Review: feat(home): hero shows three numbered points from the record, with story buttons (#1122)

## Summary

Automated review (#648) for PR #1123 on `feat/1122-home-hero-points`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `tests/test_api_data_center_positions.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/utils/heroPoints.test.ts`
- `web_app/src/utils/heroPoints.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `e60758e05bb3`.

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
