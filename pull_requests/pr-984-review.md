---
pr: 984
branch: fix/983-site-source-url
title: "fix(data-centers): no sites 500 when a registry site has no record page"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve
---

# PR Review: no sites 500 when a registry site has no record page

## Summary
Closes #983. The cause, confirmed in the API log: 206 registry rows with a null `source_url` failed the `DataCenterSite`
model. The mart now gives them the registry's dataset page (a real, credited link, not invented), the contract makes the
column `not_null`, and the API tolerates a null so one row can never break the list.

## Findings
- 🔴 None. 🟡 None.
- 🔵 The dataset-page fallback is honest (it is where the record is published) but less specific than a record page.
  Noted in the column description.

## Scans
Secrets, fabricated data, personal data, destructive changes: none.

## Tests
- dbt 29/29 locally; the endpoint returns 200 for AL.
- pytest 8 passed; `tsc` is clean.

## Verdict
**approve**: merge when the required checks are green.
