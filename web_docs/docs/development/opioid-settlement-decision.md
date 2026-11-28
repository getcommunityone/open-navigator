---
sidebar_position: 43
title: Opioid settlement spending decision
description: Inventory of official state opioid settlement reporting, the Michigan pilot that is loaded, and the free "opioid settlement" meeting topic.
---

# Opioid settlement spending decision

Issue #1396, story 4 of the peer-benchmarking epic #1392.

## What existed before

- Federal opioid-related awards were already reachable through USAspending (`federal_opioid` benchmark, story 1).
- No state settlement-fund reporting was loaded, and no "opioid settlement" curated meeting topic existed. The curated topics seed had seven topics.

## Inventory of official reporting

Reachability was tested from our environment on 27 Nov 2026 and terms must be re-read before a loader is built.

| Source | Format | Result |
|---|---|---|
| Michigan DHHS, Opioid Settlement: Settlement Spending | Excel dashboard workbook (FY22 to FY24) plus PDFs | Reachable. Loaded as the pilot. |
| Tennessee Opioid Abatement Council | Web pages | HTTP 403 to automated clients. Link out only. |
| Massachusetts opioid settlement funds | Web pages | HTTP 403 to automated clients. Link out only. |
| Virginia Opioid Abatement Authority, North Carolina DOJ, OneOhio Recovery Foundation, Washington | Web pages, award lists, PDFs | Not reachable from this environment. Not loaded. |
| Indiana Attorney General | Web pages | Page not found at the expected address. |
| State open-data portals (Socrata) | Datasets | A catalog search found no opioid settlement spending dataset. |
| Third-party trackers | Web dashboards | Their terms bar redistribution. Not used. |

## What is loaded: Michigan pilot

- `python -m ingestion.opioid_settlement.michigan` reads the state's published workbook (data as of 30 Jun 2024) into `bronze.bronze_opioid_settlement_spending`: 221 spend-plan lines with fiscal year, status, pillar, strategy, program, recipient organization, spend plan and expenditures.
- Mart `opioid_settlement_spending` (PK `opioid_line_id`, FK `jurisdiction_id` to the state jurisdiction).
- These are state-agency lines. Payments to individual cities and counties are not in the file, so a city has no value for this metric. The benchmark returns null for it, never zero.
- FY24 expenditures are not reported yet in the workbook (spend plan only), so reported spending covers FY22 and FY23.

## Meeting topic

Seed `curated_topics` gained "Opioid settlement" (`opioid-settlement`) with keywords such as opioid settlement, opioid abatement and opioid litigation. The existing free keyword full-text match over meeting transcripts links meetings to it. No paid model run.

## Next

A second state with per-recipient local data (the Virginia authority's award lists are the likeliest) once its terms are read and it is reachable.
