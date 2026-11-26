---
pr: 1107
branch: feat/1106-drilldown-stance-colours
title: "feat(stories): the state drill-down map uses the home map's colours: stance split where speakers are on record, greys by meeting count"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 7357267723b1df09e4ca0db3c99fb474fbfa8a2a
verdict: approve
---

# PR Review: feat(stories): the state drill-down map uses the home map's colours: stance split where speakers are on record, greys by meeting count

## Summary

Automated review (#648) for PR #1107 on `feat/1106-drilldown-stance-colours`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `tests/test_api_data_center_meeting_mentions.py`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/utils/boxSplit.test.ts`
- `web_app/src/utils/boxSplit.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `7357267723b1`.

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
