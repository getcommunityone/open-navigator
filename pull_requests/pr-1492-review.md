---
pr: 1492
branch: fix/1468-redact-excerpt-names
title: "fix(privacy): shorten private names and mask addresses in served meeting text"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: ae2801e3c6a7c1d5b45541b7273e2c5a6e4f7b32
verdict: approve
---

# PR Review: fix(privacy): shorten private names and mask addresses in served meeting text

## Summary

Automated review (#648) for PR #1492 on `fix/1468-redact-excerpt-names`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.github/workflows/ci-build-test.yml`
- `Dockerfile`
- `api/privacy_redaction.py`
- `api/routes/chat_meetings.py`
- `api/routes/data_center_drill.py`
- `api/routes/data_centers.py`
- `api/routes/decision_browse.py`
- `api/routes/decisions.py`
- `api/routes/lenses.py`
- `api/routes/meeting_browse.py`
- `api/routes/meeting_comparison.py`
- `api/routes/meetings.py`
- `api/routes/organizations.py`
- `api/routes/policy_questions.py`
- `api/routes/search.py`
- `api/routes/short_term_rentals.py`
- `api/routes/topic_companies.py`
- `api/routes/topic_organizations.py`
- `api/routes/topic_outcomes.py`
- `api/routes/topic_upcoming.py`
- `api/routes/topics.py`
- `api/routes/trending_terms.py`
- `dbt_project/macros/redact_person_names.sql`
- `dbt_project/models/marts/trending_term_evidence.sql`
- `packages/core-lib/src/core_lib/privacy/__init__.py`
- `packages/core-lib/src/core_lib/privacy/_given_names_data.py`
- `packages/core-lib/src/core_lib/privacy/_public_figures_data.py`
- `packages/core-lib/src/core_lib/privacy/given_names.py`
- `packages/core-lib/src/core_lib/privacy/names.py`
- `packages/core-lib/tests/test_privacy_names.py`
- `tests/test_api_data_center_job_claims.py`
- `tests/test_privacy_redaction_api.py`
- `web_docs/docs/development/privacy-and-data-ethics.md`
- `web_docs/docs/development/trending-terms-and-hot-words.md`

## CI Status

See the PR checks on `ae2801e3c6a7`.

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
