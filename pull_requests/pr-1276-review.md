---
pr: 1276
branch: chore/1272-no-outside-org-refs
title: "chore(repo): add a third-party sources rule to AGENTS.md and remove an outside organization's name from the repo"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: c250e8526474fc4dbdde5bf1924bab99b4351a8c
verdict: approve
---

# PR Review: chore(repo): add a third-party sources rule to AGENTS.md and remove an outside organization's name from the repo

## Summary

Automated review (#648) for PR #1276 on `chore/1272-no-outside-org-refs`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `AGENTS.md`
- `api/routes/search_postgres.py`
- `dbt_project/contracts/topic_meeting_lean.odcs.yaml`
- `dbt_project/models/marts/_schema_topic_meeting_lean.yml`
- `dbt_project/models/marts/mdm_organization.sql`
- `dbt_project/models/marts/topic_meeting_lean.sql`
- `dbt_project/models/staging/_staging.yml`
- `packages/llm/src/llm/typesafe/topic_lean.py`
- `packages/llm/tests/test_topic_lean.py`
- `prompts/videos/video_prompts_1.md`
- `pull_requests/pr-1257-review.md`
- `scripts/enrichment/enrich_nonprofits_logodev.py`
- `web_app/src/utils/topicPositions.test.ts`
- `web_docs/docs/development/topic-meeting-lean.md`
- `web_docs/docs/guides/form-990-enrichment.md`
- `web_docs/docs/guides/logo-enrichment.md`

## CI Status

See the PR checks on `c250e8526474`.

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
