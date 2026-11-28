---
title: USAspending federal awards decision
sidebar_label: USAspending federal awards
---

# USAspending federal awards (issue #1393, epic #1392)

## Decision

Load USAspending assistance awards (types 02 to 05) to local-government recipients, FY2019 onward, from the free API. Build `federal_award` (one row per award) and `jurisdiction_federal_funding` (one row per jurisdiction, fiscal year and assistance listing), and serve peer comparison at `GET /api/benchmark/{metric}`.

## Existing before this work

No USAspending loader, bronze table or model existed. Grants.gov opportunities (`grant_opportunity`) are a different source (what is open to apply for) and stay separate. IRS 990 `grant` is private-funder grants, also separate.

## Shape

- Loader: `python -m ingestion.usaspending.load_awards` into `bronze.bronze_usaspending_award` (upsert by `generated_unique_award_id`).
- Models: `stg_usaspending__award` -> `int_usaspending_recipient__jurisdiction_match` -> `federal_award`, `jurisdiction_federal_funding`.
- Matching: recipient name, state and kind against `jurisdictions`; each row has `match_confidence`. Unmatched awards keep a null `jurisdiction_id`. Totals are for matched awards only.
- Not loaded yet: state-government recipients and the bulk award archives.

## Not built

Per-person salaries (#1398) are not built; see that issue.
