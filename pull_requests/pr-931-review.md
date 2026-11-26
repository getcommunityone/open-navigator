---
pr: 931
branch: feat/930-who-spoke-up
title: "feat(stories): show who spoke for and against and the recorded votes, with dots on every screen and a cue toward next"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: d80d4e415ca264c177e89900dcf858b6a5a08a67
verdict: approve-with-nits
---

# PR Review: feat(stories): show who spoke for and against and the recorded votes, with dots on every screen and a cue toward next

## Summary

Adds who spoke for and against a data center item, and the recorded votes, to the Data Stories hub and story. Two new dbt marts (data_center_meeting_position, data_center_public_comment) read one intermediate view that holds the counting rule and reuses the existing data_center_regex macro; GET /api/data-centers/positions serves totals and quotes and answers available: false when the tables are not built. Every story figure becomes a dot chart, an idle cue points to the next step, and reduced motion gets opacity-only transitions. Read by the coordinator against the diff, the agent's report and phone and desktop screenshots.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

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

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- dbt has not compiled these models: packages could not be installed in the build container. The SQL was rendered by hand and run on a throwaway Postgres 16 with test rows. The owner's first dbt run is the first real compile; a failure there is a follow-up on #930, not a reason to hold the page, which degrades to 'not loaded yet'.
- Both marts declare an enforced contract, a primary key and foreign keys (to event_meeting, and from the comment table to public_comment and to the position table). The foreign key to public_comment is enforced in gold only, because public_comment is not published to public; the schema file says so.
- data_center_public_comment is an addition to the issue's contract, needed so the API reads quotes from public while the rule stays in dbt. The issue should get a dated line recording it.
- Known over-count: a comment linked to a data center decision counts even when the speaker talked about a side issue. Known misses are listed in the design note.
- Votes: every data-center decision visible on the live site has a null tally, so the vote figures may read 'not recorded' everywhere.
- ERD diagrams are not regenerated for the new tables, and api.types.ts is not regenerated (CI regenerates and type-checks).
- The challenge's charts became dots as a side effect of sharing the drawing code; not specifically asked for there.
- Fixtures used in the browser checks are outside the repo; no test numbers are in served code.

## Verdict

**approve-with-nits**
