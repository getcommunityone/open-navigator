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

## What the load skips

The load only reads files. It never moves, renames or deletes one, and a skipped file stays where it is. A file is
skipped, and counted by reason, when:

| Reason | Rule |
|---|---|
| `policy_excluded` | the video's transcript was marked `excluded:<reason>` at analysis time (promos, news, non-meetings) |
| `junk_channel` | the channel is classified junk (`bronze_youtube_channel_classification.is_junk`) |
| `non_meeting_type` | `meeting_type` is OTHER, UNKNOWN or blank |
| `low_keep_score` | the Jev keep-score `P(government_meeting) + P(town_hall)` is below `--min-meeting-p` (default 0.6); human overrides to `government_meeting` or `town_hall` win, and unscreened videos are never skipped |
| `no_event` | the video has no promoted `civic_event` row yet (run `ingestion.youtube.promote_to_c1_event`) |
| `no_meta` | the file has no metadata file of its own |
| `meta_mismatch` | its metadata was written for a different analysis file (see below) |

The first matching reason in that order is the one counted. A video with no `bronze_event_youtube` row cannot be judged
and is loaded, and counted as `unchecked_no_bronze_row`. `--no-gate` turns the skip rules off, `--tier light|full|both`
(default both) picks which files to read, and `--dry-run` reports without writing.

## Light and full never share a model

A light and a full analysis of one meeting are stored side by side, keyed by meeting and model name, so the two tiers
must use different models. Otherwise they would overwrite each other. The rule is now enforced:

- a **full** run stops before calling any model when it would run on the light tier's model (`LIGHT_MODEL`, default
  `deepseek-flash`; an empty `LIGHT_MODEL` means the Gemini default);
- a **light** run stops when it would run on `FULL_MODEL`, if that is set.

The run metadata now carries the tier in its name too: `<stem>.meta.json` for light and `<stem>_full.meta.json` for full,
and it records `analysis_tier`. Before this change a full run wrote over the light run's metadata. Files written that
way are detected by the loader (the metadata lists the other analysis file) and skipped as `meta_mismatch`, never
paired with the wrong analysis.

## The cache repair tool no longer deletes

`transcript_cache_paths._safe_move` (layout migration and basename repair) used to delete the older of two files that
map to the same name. It now moves that file into a `_superseded/` folder next to it, so no analysis is lost. A name
already taken there gets the file's modified time added.

## Still open on #796

- Storing the tier on each analysis in the database for display (a new column). It is tracked with the provenance
  footer in #798.
