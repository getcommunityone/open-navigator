---
sidebar_position: 42
title: HUD CDBG decision
description: What we load for the Community Development Block Grant, what we deliberately skip (addresses), and what HUD does not publish in a form we can fetch.
---

# HUD CDBG decision

Issue #1394, story 2 of the peer-benchmarking epic #1392.

## What existed before

USAspending awards (story 1, `federal_award`, `jurisdiction_federal_funding`) already carried CDBG grant totals under assistance listings 14.218 and 14.228 (metric `federal_cdbg`). Nothing carried activity-level spending. No HUD loader beyond the ZIP-county crosswalk existed.

## What we load

- `python -m ingestion.hud.load_cdbg` reads the HUD Open Data "Community Development Block Grant Activity" feature service (HUD-published public data) into `bronze.bronze_hud_cdbg_activity`: grantee, HUD activity group (Public Services, Housing, Public Improvements, Economic Development, Acquisition, Housing Services, Other), the matrix-code activity name, the activity funding and the completion date. About 400,000 rows since 1996.
- An activity with several sites is listed once per site with the same total. Staging keeps one row per grantee and activity so the dollars are never counted twice.
- dbt: `stg_hud_cdbg__activity`, `int_hud_cdbg_grantee__jurisdiction_match`, marts `cdbg_activity` (gold only), `cdbg_allocation` and `cdbg_activity_summary` (served, small).
- Metrics: `cdbg_allocation` and `cdbg_public_services_share` on `/api/benchmark/{metric}`.

## What we do not load

- **Addresses and point locations.** The service carries each activity's street address, ZIP and coordinates. Housing rehabilitation activities can sit at a private resident's home, so these columns are never loaded (AGENTS.md privacy rules).
- **HUD formula allocation notices.** HUD Exchange's allocation pages return HTTP 404 to automated clients and no open bulk file was found. `cdbg_allocation` is therefore built from the USAspending awards (current total obligations), and the page says so. This is an award figure, not HUD's published allocation.
- **Action Plan and CAPER documents per grantee.** HUD Exchange gives no open index we can fetch. This is left as a follow-up (an `action-item`). Grantees' own sites can be listed through the existing `jurisdiction_document` pattern later. No PDF parsing with a paid model.

## Matching

Grantees are matched to jurisdictions by name and state: the state grantee to its state (0.99), urban counties and names ending COUNTY to counties, other grantees to cities and towns (0.95 when one candidate, 0.60 when several, the most populous taken). Unmatched grantees keep a NULL `jurisdiction_id`.
