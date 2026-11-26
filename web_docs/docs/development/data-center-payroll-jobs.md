---
title: Data center payroll jobs and job-site citations
description: Why the jobs screen shows BLS payroll employment and cites the data center job boards without scraping them.
---

# Data center payroll jobs and job-site citations

Issue: [#1019](https://github.com/getcommunityone/open-navigator/issues/1019). Decision made 2026-11-25.

## What the jobs screen shows

1. **Promises:** jobs claims spoken in meetings (`job_claim`), when any are on record. Today none are.
2. **Actual payroll jobs:** BLS QCEW annual averages for **NAICS 518210** ("Computing Infrastructure Providers,
   Data Processing, Web Hosting, and Related Services"), private employers, for the scope's state and the nation.
   This is the industry BLS counts data center jobs under. It is broader than data centers alone, and the screen
   says so.
3. **Where data center jobs are tracked:** a cited list of job boards and associations.

A city scope shows its state. QCEW publishes counties, but cities aren't linked to their county here. A figure BLS
withheld (`disclosure_code = 'N'`) is null with `disclosed = false`, shown as "withheld", never as 0.

## Pipeline

- `python -m ingestion.bls.qcew` downloads `https://data.bls.gov/cew/data/api/{year}/a/industry/518210.csv` for
  2020–2024 into `data/cache/bls/qcew/`, then upserts into `bronze.bronze_bls_qcew_industry`.
- `stg_bls__qcew_industry` types the columns (integer year, withheld → null). The mart `data_center_employment` has
  one row per area (national, state, county) × year, with PK `data_center_employment_id`.
- The seed `data_center_job_sources` becomes the mart `data_center_job_source`.
- `GET /api/data-centers/job-claims` returns `employment` and `sources` alongside the claims.

## Why the job boards are cited, not scraped

Each site's terms and robots.txt were read on 2026-11-25:

| Site | Finding |
|---|---|
| Data Center JobHub | Terms: "Do not scrape, bulk-copy or resell the listings." |
| Data Center Job Market | Terms forbid automated access "without our written consent". |
| DataCentersCareers.com | Terms: "No scraping, automated extraction, or bot access." |
| Work In Data Center | Terms forbid "automated bots, scrapers, or data mining tools". |
| DC Job Board | No scraping clause, but it republishes employers' public listings. Cited only. |
| DataCenterJobs.us | No listings yet ("Coming soon"). |
| 7x24 Exchange Career Center | The job board couldn't be read. Cited only. |
| AFCOM Career Center | afcom.com returned 403. Not listed until its URL is confirmed. |

Listings from a board whose terms forbid automated collection are never pulled. To add live postings, ask a board
for a feed or API (or permission), or read employers' own career pages where their terms allow it.
