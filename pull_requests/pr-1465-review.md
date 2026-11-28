---
pr: 1465
issue: 1443
branch: feat/1443-body-membership
title: "feat(dbt): body_membership with roles from officials, Legistar office records, rosters and OpenStates"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1465 review

Reviewed against `.claude/review-rubric.md`.

## Summary

Adds the Legistar body-membership reader, two staging views, `int_body_member__candidate` and the `body_membership`
mart, and widens `governing_body` to bodies known from rosters. It runs on the local warehouse (24/24 Legistar
portals, 10,121 memberships; Tuscaloosa's mayor and six seated members with districts and the District 5 vacancy).
Role and name-key twins agree on 14,865 real rows. Approve with nits.

## Scans

- Secrets: clean. Fabricated data: clean (members come only from rosters; a vacancy stays a vacancy).
- Personal data: officials and appointees in their public role only; the Legistar office email is deliberately not
  stored (asserted in `test_parse_office_record_drops_email`). No residents.
- Destructive data changes: the reader replaces a portal's current office records on a successful read only (a
  failed read keeps the last set). New tables otherwise.
- Scraping: PoliteClient (robots.txt, honest UA, 1 req/s, stop on 403/429), tested with MockTransport.

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- Legistar members are tied to `person_government` only on an exact name key (2 of 2,197 matched), so most have no
  person page link yet. Promoting Legistar members into `contact_official` is a follow-up (#1441 tracks it).
- `int_meeting_body__matched` now uses the AI body name only for videos that read as meetings (fixes interviews filed
  under a council); covered by the next `dbt run`.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, branch/PR naming | Yes | #1443 |
| New loaders in packages, polite scraping | Yes | `scrapers.platforms.legistar_people` |
| Transformations in dbt; PK/FKs | Yes | contracts enforced; FKs to governing_body, person_government, legislator |
| Privacy | Yes | public roles only; no email stored |
| Docs with the change | Yes | decision page section "Members and roles" |

## Test Coverage

pytest 81 passed (roles, name keys, Legistar parsing, block/robots behaviour, title twin). dbt run + test PASS=24.

## Verdict

approve-with-nits.
