---
title: What production serves from Neon
description: Why the 990 money graph and raw bills aren't in production, and how the app shows that.
---

# What production serves from Neon

**Decision (2026-11-14, [#284](https://github.com/getcommunityone/open-navigator/issues/284)):** production reads
Neon, and Neon carries only the civic serving tables. The nonprofit and 990 money graph is not copied there, and the
pages that need it show as unavailable.

## Why

Neon's free tier caps the whole project at 512 MB. The 990 money graph is about 5 GB: `grant` alone is about 2.3 GB,
and `mdm_organization`, `mdm_organization_nonprofit`, `mdm_bridge_org_jurisdiction` and `nonprofit_sector_revenue`
add the rest. Raw OpenStates `bills` and `bill_sponsorship` are about 1.8 GB more. The list, with sizes, is
`NON_SERVING` in [`sync_public_to_neon.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/hosting/src/hosting/neon/sync_public_to_neon.py).

## What users see

- **Follow the money:** the *grants* and *economy* lenses are empty in production. The other lenses don't use these
  tables. No stand-in numbers are shown (`CLAUDE.md`, "No Fabricated Data").
- **The API:** `api/routes/money_flow.py` notices the missing table on the first request, logs it once at INFO, and
  stops querying it until the process restarts. Before #284 it logged a warning on every request.
- **Locally**, against the full warehouse, every lens works.

## When to revisit

If production moves to a database without the 512 MB cap (a paid Neon plan, Lakebase or another Postgres), add the
tables to the copy list in `sync_public_to_neon.py`, run
`python -m hosting.neon.sync_public_to_neon --only grant nonprofit_sector_revenue`, and restart the API.
