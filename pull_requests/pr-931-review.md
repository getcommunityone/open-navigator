---
pr: 931
branch: feat/930-who-spoke-up
title: "feat(stories): show who spoke for and against and the recorded votes, with dots on every screen and a cue toward next"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: d80d4e415ca264c177e89900dcf858b6a5a08a67
verdict: approve
---

# PR Review: feat(stories): show who spoke for and against and the recorded votes, with dots on every screen and a cue toward next

## Summary

Automated review (#648) for PR #931 on `feat/930-who-spoke-up`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `dbt_project/contracts/data_center_meeting_position.odcs.yaml`
- `dbt_project/contracts/data_center_public_comment.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/_schema_int_data_centers.yml`
- `dbt_project/models/intermediate/int_data_center__public_comment.sql`
- `dbt_project/models/marts/_schema_data_center_meeting_position.yml`
- `dbt_project/models/marts/data_center_meeting_position.sql`
- `dbt_project/models/marts/data_center_public_comment.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/hosting/tests/test_neon_sync_data_center_tables.py`
- `tests/test_api_data_center_positions.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/stance.ts`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/Cover.tsx`
- `web_app/src/components/stance/FloatingNext.tsx`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/components/stance/SentenceHeading.tsx`
- `web_app/src/components/stance/SidesBlock.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/hooks/useIdleNudge.ts`
- `web_app/src/pages/Challenge.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/idleNudge.test.ts`
- `web_app/src/utils/idleNudge.ts`
- `web_app/src/utils/stanceGame.test.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/development/data-center-who-spoke-up.md`
- `web_docs/docs/guides/data-center-challenge.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `d80d4e415ca2`.

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
