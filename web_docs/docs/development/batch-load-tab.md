---
sidebar_position: 47
title: Batch Job Status tabs - Extract Transform, Load, Deploy
description: The three tabs on Admin → Batch Job Status, and how the Load tab moves analyses from saved files into the gold tables (#796).
---

# Batch Job Status tabs

Issue [#796](https://github.com/getcommunityone/open-navigator/issues/796).

**Admin → Batch Job Status** has three tabs, in the order the data moves:

| Tab | What it does | Where it writes |
|---|---|---|
| **1 Extract Transform** | The YouTube pipeline: Discover, Videos, Transcripts, Analysis light, Reports light (and the opt-in full stages). Formerly "YouTube pipeline". | Analysis and report **files** under `data/cache/gemini_transcript_policy`, plus progress stamps |
| **2 Load** | Loads the saved analyses into the database and rebuilds the gold tables. | Local warehouse only |
| **3 Deploy** | Publishes the local serving objects to production. Formerly "Prod deployment". | Neon prod, and optionally HuggingFace |

Deep links: `?type=load` and `?type=deployment` (tab 1 has no parameter).

## Tab 2: Load

Two steps run in order. A failing step stops the run, and **Stop** ends the running step.

1. **Load analyses - files → bronze** runs `python -m llm.enrichment.load_analysis_cache_to_bronze`. It reads the saved
   `02_analysis/*.json` files and upserts them into `bronze.bronze_events_analysis_ai`. It only reads files; it never
   moves, renames or deletes one.
2. **Rebuild gold - dbt** runs `dbt run --select int_preferred_event_analysis+ bronze_decisions_from_ai+`. That rebuilds
   `event_decision`, `event_meeting`, `event_topic`, `event_place` and the other marts that read the analysis, then the
   `on-run-end` hook refreshes the `public` views the website reads.

The **Dry run** box logs the commands without running them. The Load tab has no production switch: it never touches
production. A real **Deploy** still needs `DEPLOYMENTS_ALLOW_LAUNCH=1` on the API.

The dbt executable is found in this order: `DBT_BIN`, `dbt_project/.venv_dbt/bin/dbt`, `.venv-dbt/bin/dbt`,
`dbt_project/.dbtenv/bin/dbt`, then `dbt` on the PATH.

Load and Deploy are separate job kinds: one of each can run at the same time, but two of the same kind cannot, and a
job never mixes the two kinds.

## Not in this change yet (still open on #796)

- Skipping videos that are not government meetings during the load (meeting type, junk channel, policy exclusions,
  Jev keep-score), with a count per reason.
- Keeping the light run's metadata: a full run currently writes the same `04_runs/<stem>.meta.json` as the light run.
- A guard that stops a full run on the same model as the light tier.
- The cache repair tool keeping older duplicates instead of deleting them.

Until the skip rules land, the load takes every analysis file it finds.
