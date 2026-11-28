---
pr: 1439
branch: fix/1428-dc-over-time-all-sites
title: "fix(stories): Over time map shows every data center site, with a listed-by date basis"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 465e7e9257189ed8427bcdb29da6caa99ed0119c
verdict: approve
---

# PR Review: fix(stories): Over time map shows every data center site, with a listed-by date basis

## Summary

Automated review (#648) for PR #1439 on `fix/1428-dc-over-time-all-sites`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_center_sites_timeline.py`
- `dbt_project/models/marts/_schema_data_center_site_timeline.yml`
- `dbt_project/models/marts/data_center_site_timeline.sql`
- `tests/test_api_data_center_sites_timeline.py`
- `web_app/e2e/over-time-all-sites.check.mjs`
- `web_app/src/api/sitesTimeline.ts`
- `web_app/src/components/stance/SitesTimelinePanel.css`
- `web_app/src/components/stance/SitesTimelinePanel.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/utils/screenBoxes.ts`
- `web_app/src/utils/siteTimeline.test.ts`
- `web_app/src/utils/siteTimeline.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `465e7e925718`.

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
