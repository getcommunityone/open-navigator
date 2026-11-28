---
sidebar_position: 40
title: State grants, municipal budgets and ACFR source inventory
description: Which state grant portals, municipal budget sources and annual financial reports are viable to ingest, with coverage, terms and cost. Inventory only.
---

# State grants, municipal budgets and ACFR source inventory

Issue #1397, story 5 of the peer-benchmarking epic #1392. This page is an inventory. No code and no ingest came with it. Terms are summarized from each publisher's public pages as of 27 Nov 2026 and must be re-read before anyone builds a loader (the build issue records the terms it read).

## What we already have (do not duplicate)

| Source | Where | Grain |
|---|---|---|
| Census Annual Survey of State and Local Government Finances | `jurisdiction_finance`, `jurisdiction_finance_category` marts | government x year x category |
| USAspending federal assistance awards | `federal_award`, `jurisdiction_federal_funding` (#1393) | award; jurisdiction x FY x ALN |
| Grants.gov federal opportunities | `grant_opportunity` | opportunity |
| IRS 990 grants (private funders) | `grant` mart | grant |

Not covered yet: grants a state makes to cities, counties and school districts; line-item adopted budgets; audited annual financial reports (ACFR) at the fund and function level.

## State grant awards to local governments

| Source | Coverage | Format | Terms | Cost | Viable |
|---|---|---|---|---|---|
| Federal Audit Clearinghouse (FAC) single audits, api.fac.gov and the FAC downloads | Every non-federal entity that spends 750k dollars or more in federal awards (the threshold is 1M dollars from FY2025). Gives federal and some state awards expended by each city, county, district. | Public API and bulk files | U.S. government work, public domain | Free, key for the API | Yes. Best next source: complements USAspending with the recipient's own audited expenditure and the audit findings |
| California Grants Portal (grants.ca.gov) | Opportunities and awards of California agencies | CSV and API on the state open data portal | California open data terms; check licence on each dataset | Free | Yes, one state |
| Texas Comptroller, Texas Transparency | State payments to vendors and local governments | Search UI, downloads | State public information; automated collection terms to be checked | Free | Maybe |
| New York Open Book (Office of the State Comptroller) and Grants Gateway | State aid and local government finance | Socrata open data (data.ny.gov) | Open Data terms of use | Free | Yes, one state |
| Other state "checkbook" portals (Ohio, Illinois, Florida, Pennsylvania and others) | Varies, many are state spending only, not by local recipient | Search UI, some CSV | Varies | Free | Build one state at a time and only where a bulk or API route exists |

## Municipal budgets and annual financial reports

| Source | Coverage | Format | Terms | Cost | Viable |
|---|---|---|---|---|---|
| Census Annual Survey of State and Local Government Finances | All large governments, sample of small | Bulk files | Public domain | Free | Already loaded |
| California State Controller, By The Numbers (bythenumbers.sco.ca.gov) | Cities, counties, special districts: revenue, expenditure by category | Socrata open data | Open data terms | Free | Yes, one state, full coverage |
| New York OSC local government data | Cities, towns, villages, counties, districts | Socrata open data | Open Data terms | Free | Yes |
| Other state comptroller or auditor reports (Ohio, Pennsylvania, Texas, Florida, Michigan) | Annual financial reports for local governments | PDF or spreadsheet | Public records; terms vary | Free | One state per story; PDF parsing needs no paid model |
| MSRB EMMA (emma.msrb.org) | Official statements and ACFRs filed for municipal bond issuers | Web site | The EMMA terms restrict automated collection and redistribution | Free to view | No. Link out only, never scrape |
| Government Finance Officers Association ACFR award lists | Names of governments with a Certificate of Achievement | Web pages | Copyright of GFOA | Free | Link out only |
| Open-budget platforms (OpenGov, ClearGov, Socrata Open Budget, Balancing Act) | Per-city budget explorers, thousands of cities | Hosted web apps, some with an export or API | Each vendor's terms; the budget is public but the platform terms usually bar bulk scraping | Free to view | Per city, with a written terms check; prefer the city's own published budget PDF |
| City adopted-budget PDFs on city sites | Every city | PDF | Public record | Free | Fits the existing `jurisdiction_document` pattern (document links, no paid-LLM parsing) |

## Recommendation: build next

1. **Federal Audit Clearinghouse single audits.** Free, public domain, covers every city and county that spends federal money, one national format, and joins to our jurisdictions the same way as USAspending. It adds expenditure by program and audit findings.
2. **California State Controller By The Numbers.** Full coverage of one large state in an open, documented format; gives the first line-item revenue and expenditure comparison for peers.
3. **New York OSC local government data.** Same pattern, second state, tests the loader on a different schema.

All three follow the same rules as the others: package CLI under `ingestion/`, bronze then dbt, `match_confidence` where names are matched, no paid model runs.

## Do not build

- Anything from MSRB EMMA.
- Bulk scraping of a vendor budget platform whose terms forbid it.
