---
pr: 1067
branch: feat/1062-tuscaloosa-official-contacts
title: "feat(officials): Tuscaloosa council members' public office emails, with source; Tyner marked no longer in office"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 660e0aa6067352840495d36d8f62c38c330ba85d
verdict: approve
---

# PR Review: feat(officials): Tuscaloosa council members' public office emails, with source; Tyner marked no longer in office

## Summary

Automated review (#648) for PR #1067 on `feat/1062-tuscaloosa-official-contacts`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/models/marts/_schema_contact_official.yml`
- `dbt_project/models/marts/_schema_person_government.yml`
- `dbt_project/models/marts/contact_official.sql`
- `dbt_project/models/marts/person_government.sql`
- `dbt_project/seeds/official_contact_override.csv`
- `dbt_project/seeds/schema.yml`
- `web_docs/docs/development/official-contacts.md`

## CI Status

See the PR checks on `660e0aa60673`.

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

- Story: Refs #1062 (claim flow follows); epic #1061 table in the body.
- Scans: no secrets. Personal data: only official work addresses copied verbatim from the city's own pages (public records), each with source URL and verified date; the public serving projection still redacts email and phone, so nothing new is served. No fabricated data: no address is built from a pattern; missing stays null.
- Correctness: the override joins on name + state + jurisdiction, so a same-named official elsewhere is untouched; is_current=false for Kip Tyner is sourced to the council page (District 5 vacant, memorial link). Local build of contact_official/person_government passed; ODCS contracts current.
- Docs: official-contacts.md.

No blocking findings.
