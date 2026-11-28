---
sidebar_position: 41
title: Census ASPEP public payroll decision
description: What the Census Annual Survey of Public Employment and Payroll gives us (aggregate only, never per-person pay), and the state open-payroll portals and privacy plan for any per-person data.
---

# Census ASPEP public payroll decision

Issue #1395, story 3 of the peer-benchmarking epic #1392. The per-person question is #1398 (owner decision, not built).

## What ASPEP contains, and what it does not

The Census Annual Survey of Public Employment and Payroll (ASPEP) reports, for each government and each functional category (police, fire, highways, parks and others): full-time and part-time employees, and the March payroll (31-day monthly equivalent, dollars).

**ASPEP does NOT contain department-head salaries or any per-person pay.** There is no name, no title and no individual in the files. An "average monthly pay" is payroll divided by employees: an average over a workforce. The site must not present it as what any person earns. A question such as "compare my police chief's salary with peers" cannot be answered from this source.

## What we built

- Loader: `python -m ingestion.census.load_aspep` reads the Census individual unit files (public domain, no key) for 2019, 2020, 2021, 2023 and 2024 into `bronze.bronze_aspep_unit` and `bronze.bronze_aspep_employment`. Census year 2022 is published under a different file name and is not loaded yet.
- dbt: `stg_aspep__unit`, `stg_aspep__employment`, seed `aspep_function_code`, `int_aspep_unit__jurisdiction_match`, mart `jurisdiction_public_payroll` (grain jurisdiction x year x function, PK and FK to `jurisdictions`), and the served slice `jurisdiction_public_payroll_latest` (latest year, twelve core functions, under 5 MB).
- Matching: counties by FIPS (0.99), states (0.99), municipalities and townships by normalized name and state with the closest population among ties (0.95 unique, 0.60 ambiguous). School districts and special districts are not matched.
- API: `GET /api/benchmark/{metric}` metrics `payroll_total`, `payroll_police` and `avg_pay_all_functions`.
- Years that do not end in 2 or 7 are samples. A government missing in those years was not sampled; it did not report zero.

## Open-payroll portals (inventory only, nothing ingested)

State portals publish named individuals' pay. They are listed so the owner can decide in #1398. Terms must be re-read before any build.

| Portal | Coverage | Format | Terms (to verify) |
|---|---|---|---|
| Texas Tribune and state comptroller payroll data | State employees | Search, downloads | Public information; check automated-use terms |
| California State Controller, Government Compensation in California (publicpay.ca.gov) | State, cities, counties, special districts: pay per position | Search and CSV downloads | State open data terms |
| Ohio Checkbook, Illinois, Florida and Pennsylvania state payroll sites | State employees, some local | Search UIs, some CSV | Vary by state |
| OpenPayrolls, TransparentCalifornia and similar aggregators | Many governments | Scraped copies | Third parties. Their terms forbid scraping. Not used. |

## Privacy plan if per-person data is ever approved

These follow AGENTS.md, "Privacy and data ethics".

- Only officials and staff in their public role. No private person is ever enriched with a home address, workplace or any personal detail.
- Only the official source's published fields (role, department, pay) with the source link. No inference of any trait.
- Names appear only for public officials in office. Rank-and-file names are out unless the owner decides otherwise in #1398.
- No third-party aggregator that bars scraping. Official portals only, slow, identified as `open-navigator`, stop on 403 or 429.
- Removal and correction requests are honoured (see the privacy page).

No per-person data is ingested by this change.
