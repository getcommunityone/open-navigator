---
pr: 1147
branch: fix/1139-concerns-aggregate
title: "fix(stories): Concerns screen shows each concern once per state, with the towns and a national comparison (#1139)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 23ff8aed8f8a29afa57b20d92eeb76596eeee621
verdict: approve
---

# PR Review: fix(stories): Concerns screen shows each concern once per state, with the towns and a national comparison (#1139)

## Summary

Automated review (#648) for PR #1147 on `fix/1139-concerns-aggregate`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `tests/test_api_data_center_concerns.py`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/utils/concernsHeadline.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/houseTheme.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/development/data-center-local-concerns.md`

## CI Status

See the PR checks on `23ff8aed8f8a`.

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
