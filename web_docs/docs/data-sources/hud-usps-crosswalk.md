---
title: "HUD USPS ZIP Crosswalk"
description: "HUD–USPS ZIP Code Crosswalk Files mapping ZIP codes to counties (and other geographies), used to attach addresses to jurisdictions."
tags: [data-source, hud, geography, jurisdictions]
---

# HUD USPS ZIP Crosswalk

**Authoritative ZIP-to-county mapping from HUD and the USPS.**

The HUD–USPS ZIP Code Crosswalk Files map each USPS ZIP code to the county
(and other Census geographies) it falls in, along with the share of
residential, business, and other addresses in each. Open Navigator uses the
ZIP→county crosswalk to resolve addresses to the counties and jurisdictions
they belong to.

:::info At a glance
| | |
|---|---|
| **Provider** | U.S. Department of Housing and Urban Development (HUD), Office of Policy Development and Research |
| **Coverage** | All U.S. ZIP codes; quarterly snapshots |
| **Update cadence** | Quarterly |
| **License** | Public domain (U.S. government work) · see [Legal](../legal/index.md) |
| **Cost** | Free — **requires a free HUD User login to download** |
| **Access method** | Bulk `.xlsx` download (cached locally) |
| **Our pipeline** | `bronze.bronze_jurisdictions_zip_county` · `packages/ingestion/src/ingestion/hud/zip_county.py` |
:::

## Overview

HUD publishes quarterly crosswalk files derived from USPS address data that
relate ZIP codes to a range of Census geographies (county, tract, CBSA,
congressional district, and more). We use the **ZIP→county** file: it gives,
for every ZIP code, the county or counties it overlaps and the proportion of
addresses in each.

Because a single ZIP code can span multiple counties, each row carries
residential, business, other, and total address ratios so downstream models
can pick the dominant county or weight by address share.

## Data available

### Fields

| Field | Description | Type | Coverage |
|-------|-------------|------|----------|
| **zip** | 5-digit USPS ZIP code | `char(5)` | 100% |
| **county** | 5-digit county FIPS code | `char(5)` | 100% |
| **usps_zip_pref_city** | USPS preferred city name for the ZIP | `varchar(100)` | ~100% |
| **usps_zip_pref_state** | USPS preferred 2-letter state code | `char(2)` | ~100% |
| **res_ratio** | Share of residential addresses in this county | `numeric` | 100% |
| **bus_ratio** | Share of business addresses in this county | `numeric` | 100% |
| **oth_ratio** | Share of other addresses in this county | `numeric` | 100% |
| **tot_ratio** | Share of all addresses in this county | `numeric` | 100% |

### Grain & keys

- **Grain:** one row per ZIP code × county overlap
- **Primary key:** `(zip, county)`
- **Joins to:** addresses on `zip` (see `mdm_bridge_address_county`), and onward
  to counties/jurisdictions on the county FIPS code

## How we ingest it

```bash
# Load the latest cached crosswalk into bronze (full reload):
python -m ingestion.hud.zip_county --truncate

# Or load a specific snapshot / a sample:
python -m ingestion.hud.zip_county --file data/cache/hud/ZIP_COUNTY_122025.xlsx --limit 500
```

- **Source:** https://www.huduser.gov/portal/datasets/usps_crosswalk.html
  (download requires a free HUD User account)
- **Lands in:** `bronze.bronze_jurisdictions_zip_county` → `mdm_bridge_address_county`
- **Refresh:** download the newest quarterly `ZIP_COUNTY_<MMYYYY>.xlsx` into
  `data/cache/hud/`, then re-run the loader with `--truncate`

## Coverage & known gaps

- The download is gated behind a free HUD User login, so it cannot be fetched
  unattended — the loader reads a manually-cached `.xlsx` from `data/cache/hud/`.
- ZIP codes that span county lines produce multiple rows; consumers must decide
  whether to take the dominant county (`tot_ratio`) or weight by share.
- ZIP codes are a USPS delivery construct, not a true geography, so a small
  number of edge cases (PO-box-only or point ZIPs) map imperfectly to counties.

## Licensing & attribution

The crosswalk files are produced by a U.S. federal agency and are in the public
domain. HUD requests attribution to the *HUD–USPS ZIP Code Crosswalk Files*.
See the provider's [dataset page](https://www.huduser.gov/portal/datasets/usps_crosswalk.html)
for the full terms.

## Related

- [Census shapefiles](./census-shapefiles.md)
- [Jurisdiction discovery](./jurisdiction-discovery.md)
- [Data model ERD](./data-model-erd.md)
