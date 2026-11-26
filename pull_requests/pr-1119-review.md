---
pr: 1119
branch: feat/1117-maps-public-lean
title: "feat(stories): maps show where the public leaned against data centers (AI reading) and where officials sided against the public"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: cefafd34c1180e71a045c176a0bc38962e0c6b6d
verdict: approve
---

# PR Review: feat(stories): maps show where the public leaned against data centers (AI reading) and where officials sided against the public

## Summary

Automated review (#648) for PR #1119 on `feat/1117-maps-public-lean`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `dbt_project/contracts/data_center_meeting_lean.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_data_center_meeting_lean.yml`
- `dbt_project/models/marts/data_center_meeting_lean.sql`
- `dbt_project/models/staging/stg_jev__transcript_screen.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `tests/test_api_data_center_meeting_mentions.py`
- `tests/test_api_data_center_positions.py`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/home/storyColors.test.ts`
- `web_app/src/components/home/storyColors.ts`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/lib/api.types.ts`
- `web_docs/docs/development/data-center-meeting-lean.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `cefafd34c118`.

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
