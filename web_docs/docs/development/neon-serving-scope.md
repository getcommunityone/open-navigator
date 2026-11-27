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
- **Locally**, against the full warehouse, every lens works. The default dbt selector
  (`local_warehouse` in `dbt_project/selectors.yml`) skips `grant` and `serving_grant`
  because filtering ~6.7M Schedule I rows against ~234k kept orgs took >36 minutes on
  the laptop warehouse before cancel ([#607](https://github.com/getcommunityone/open-navigator/issues/607)).
  Build them explicitly with `dbt run --select serving_grant` when preparing a Neon publish.

## When to revisit

If production moves to a database without the 512 MB cap (a paid Neon plan, Lakebase or another Postgres), add the
tables to the copy list in `sync_public_to_neon.py`, run
`python -m hosting.neon.sync_public_to_neon --only grant nonprofit_sector_revenue`, and restart the API.

## The size check before each sync

Allow-listed tables still grow with every crawl, so `python -m hosting.neon.sync_public_to_neon` checks the size
before it copies anything ([#387](https://github.com/getcommunityone/open-navigator/issues/387)):

- It estimates each incoming table from the local rows (column sizes plus Postgres's per-row overhead).
- It reads Neon's current size and projects the size after the swap, and the peak while a staging copy and the old
  table both exist.
- It stops with exit code **4**, before touching Neon, when the projected size passes **480 MB** (`--max-mb` or
  `NEON_MAX_MB`) or the peak passes the 512 MB cap. The log lists the largest incoming tables.
- `--dry-run` prints each table's estimated size and the total.

The data center tables (`job_claim`, `data_center_site`, `data_center_agenda_item`, `area_concern`) are on the
allow-list. `job_application_link` is written by the production admin screen, so it is runtime-owned and never copied.

`recorded_meeting_year` (recorded meetings per place and year, about 1 MB) is on the allow-list too
([#1194](https://github.com/getcommunityone/open-navigator/issues/1194)). The story timelines and the dumbbell use it to
tell a real zero year from a year with no recordings; without it production draws those years as gaps. It was first
published on November 26, 2026 with `--only recorded_meeting_year` (8,076 rows; Neon 363 MB to 364 MB).

`meeting_video_kind` (one row per video: whether it is a public meeting, from Jev's existing screen) is on the allow-list too ([#1258](https://github.com/getcommunityone/open-navigator/issues/1258)). The story map cards quote only real meetings with it (#1240); without it production falls back to the newest passage, interviews included. First published on November 27, 2026 with `--only meeting_video_kind` (6,264 rows; Neon 367 MB to 368 MB).

## Decision: production serving stays on Neon (November 15, 2026)

The owner decided to keep production serving on Neon and not move it to Databricks Lakebase
([#389](https://github.com/getcommunityone/open-navigator/issues/389)).

- **Why:** Neon's free tier costs nothing, and the size check above keeps each sync under its 512 MB cap. Lakebase
  would remove the cap but bills for compute and storage, and the public API would keep it awake.
- **What Databricks can still do:** processing that shouldn't depend on the laptop (the analysis bundle and the
  [Free Edition target](../deployment/databricks-free-edition.md)), never production serving.
- **YouTube captions** stay on a residential connection or proxy either way; cloud IP addresses are blocked more.
- **Revisit** if the civic serving set can't fit under the budget without cutting what users need, or if a paid
  database becomes affordable.
