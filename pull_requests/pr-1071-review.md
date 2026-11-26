---
pr: 1071
branch: feat/1062-official-claim-flow
title: "feat(people): officials can claim their profile and propose edits"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 8ee62db84d095062f374ea8cf7845c95eb811d0b
verdict: approve
---

# PR Review: feat(people): officials can claim their profile and propose edits

## Summary

Automated review (#648) for PR #1071 on `feat/1062-official-claim-flow`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/app.py`
- `api/main.py`
- `api/models.py`
- `api/routes/person_claims.py`
- `dbt_project/contracts/person_government.odcs.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_person_government.yml`
- `dbt_project/models/marts/person_government.sql`
- `tests/test_api_person_claims.py`
- `web_app/src/api/personClaims.ts`
- `web_app/src/components/ClaimProfile.tsx`
- `web_app/src/pages/PersonDetail.tsx`
- `web_docs/docs/development/people-claim-and-privacy.md`

## CI Status

See the PR checks on `8ee62db84d09`.

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

## Agent review

- Story #1062 under epic #1061; follow-up #1070 (owner review screen).
- Scans: no secrets; no email or hash returned or logged (read person_claims.py logging); email stays redacted in public serving, only its sha256 is served (official addresses are public records anyway); no fabricated data.
- Correctness: hmac.compare_digest; defensive to_jsonb read of email_sha256; edits pending; title/bio/photo only on verified claims; https-only photo; another user's claim -> 404.
- Checks: pytest 10 passed (re-run by me), tsc clean, ODCS current, local dbt build passed after merging #1067.

No blocking findings.
