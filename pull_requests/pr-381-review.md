---
pr: 381
branch: feat/247-claim-attribution
title: "feat(dc): DC-1.2 attribute each jobs claim to its speaker, role and meeting moment"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: DC-1.2 claim attribution (#381)

## Summary
Each data center jobs claim now names its speaker and their role (as said in the meeting), the governing body that met and the date, and links to the moment on the in-app meeting page through the shared `CitationLink` (#240). The change runs from the prompt through staging, mart, API and page, and the contract and generated types are regenerated. It meets #247's "Done when" for claims extracted with the new prompt. Older analyses show the name only until re-analyzed. Approve with nits.

## Scope of Change
- dbt: `stg_job_claim_ai` (role, `people[]` fallback), `job_claim` (`speaker_role`, `body_name`), both schema files, the regenerated `job_claim.odcs.yaml`.
- Prompt: `policy_analysis_part_1.md` (`job_claims[].speaker_role`, `speaker_person_id`).
- API: `api/routes/data_centers.py` (two response fields).
- Web: `DataCenters.tsx`, `dataCenterJobs.ts` (+ test), `api.types.ts` (only the `JobClaim` block).
- Docs: `data-center-jobs.md`.

## CI Status
Checked on the head commit once CI completes; see the PR's Checks tab.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: none.
- Fabricated data: none. Every new value is null when unknown ("Speaker not identified", "time not recorded", "Meeting record"), and the role is never inferred from a name.
- Personal data: speaker names and roles come from public meeting records, as before.
- Destructive changes: none. Columns are added only, and `job_claim_id` is unchanged.

## Strengths
- Reuses `CitationLink` and `meetingMomentPath` instead of a second citation format.
- The `people[]` fallback is in dbt (JSONB extraction stays in SQL, per CLAUDE.md) and is guarded against a non-array `people`.
- The stable primary key means existing claim ids and links survive the change.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None. A lost `/person/:id` link (the old card linked a resolved speaker) was found during review and restored on this branch as "More from <name>".
### 🔵 Nits / suggestions (Minor)
- `hearItUrl` (external YouTube link) is no longer used by the page; it stays exported and tested. Remove it once no other surface needs a YouTube link.
- `people[].role` can be a long phrase ("Applicant representative, Project Blue LLC"); `CitationLink` shows it in full. Fine for now; truncate if it crowds the card.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first, four parts, Contract line before first commit | ✅ #247, Contract comment 2026-11-15 |
| Branch `<type>/<issue>-<slug>`, `Closes #247` | ✅ |
| Conventional Commits | ✅ |
| Transformations in dbt, not Python | ✅ |
| PK/FK on `public` relations | ✅ unchanged (PK `job_claim_id`, FK `jurisdiction_id`) |
| No fabricated data | ✅ |
| Scope label rule | ✅ unchanged; `?state=&city=` still drives label and query |
| Docs in `web_docs/docs/` | ✅ |

## Test Coverage
- API: 2 new tests (fields served; SELECT reads them); 22 pass.
- Web: `meetingAttribution` tests; 38 pass with `timestamp`. `tsc` and eslint clean.
- dbt: compiled and parsed. The staging logic ran on stub rows covering a stated role, a `people[]` fallback and an unmatched reference.
- Not covered: a run on the real warehouse (`dbt build --select +job_claim`).

## Verdict
**approve-with-nits.**
