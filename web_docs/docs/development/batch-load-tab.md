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

Three steps run in order. A failing step stops the run, and **Stop** ends the running step.

1. **Promote events - videos → civic_event** (#827) runs
   `python -m ingestion.youtube.promote_to_c1_event --local-warehouse`. An analysis can only be stored against an event
   row, so this step gives every analysed video one before the load looks for it. Without it those analyses are
   skipped as `no_event`. It upserts on the video id, so running it again changes nothing. It promotes only videos
   that have an analysis stamp and a date, never the raw scrape. `--local-warehouse` makes it write to the database
   the loader uses (`NEON_DATABASE_URL_DEV`, else `localhost:5433`) and never to `NEON_DATABASE_URL`; without that
   flag the command's own default can resolve to production. Untick the step to skip it.
2. **Load analyses - files → bronze** runs `python -m llm.enrichment.load_analysis_cache_to_bronze`. It reads the saved
   `02_analysis/*.json` files and upserts them into `bronze.bronze_events_analysis_ai`. It only reads files; it never
   moves, renames or deletes one.
3. **Rebuild gold - dbt** runs
   `dbt run --select int_preferred_event_analysis+` plus every `bronze_*_from_ai` model that reads the analysis table,
   with its descendants
   (meetings, decisions, topics, places, persons, organizations, bills, financial items, causes, public
   participation). Each of those bronze
   models reads the analyses the load step just wrote, and the marts read them, so all of them have to be in the
   selection (#836). Before, only `bronze_decisions_from_ai+` was: `event_meeting`, `event_topic` and the rest were
   rebuilt from bronze tables the step had not refreshed, and `public_comment` failed outright. A new
   `bronze_*_from_ai` model must be added to the step; a test fails until it is. That rebuilds
   `event_decision`, `event_meeting`, `event_topic`, `event_place` and the other marts that read the analysis, then the
   `on-run-end` hook refreshes the `public` views the website reads.

The **Dry run** box logs the commands without running them. The Load tab has no production switch: it never touches
production. A real **Deploy** still needs `DEPLOYMENTS_ALLOW_LAUNCH=1` on the API.

The dbt executable is found in this order: `DBT_BIN`, `dbt_project/.venv_dbt/bin/dbt`, `.venv-dbt/bin/dbt`,
`dbt_project/.dbtenv/bin/dbt`, then `dbt` on the PATH.

Load and Deploy are separate job kinds: one of each can run at the same time, but two of the same kind cannot, and a
job never mixes the two kinds.

## Counts and the drill-down (#823)

Each step of a Load run records what it did, and the tab shows it the way tab 1 shows its stages.

| Where | What you see |
|---|---|
| A run's header | `N files read · N loaded · N skipped · N file errors`, then `N of N models built` once dbt has run |
| A step's row | count chips: videos, events, recordings for promotion; read, loaded, skipped, errors for the loader; models, built, skipped, failed for dbt |
| An opened step | every reason with its count and what to do about it, a search box, and a paged table of the items: outcome, reason, file (with a link to the video), and the error text |

Click a reason to filter the table to it. Errors are listed before skips, in the reasons and in the table. The log tail stays below the table.

A step shows **No counts recorded for this run** when it left no result: runs from before #823, dry runs (no command
is executed), and a step that crashed before it could write. It never shows zeros it did not measure.

How it works:

- The loader takes `--result-json PATH` and writes its counts plus one entry for every file it did **not** load. The
  job runner passes the path, `data/cache/batch_jobs/deployments/<job_id>_load-analysis.result.json`, next to the log.
- After the dbt step, the runner reads dbt's own `dbt_project/target/run_results.json` and writes
  `<job_id>_dbt-gold.result.json` with each model that failed or was skipped and dbt's message. If that file is older
  than the step (left by another dbt run), nothing is recorded.
- `GET /api/deployments/{job_id}/result?step=&outcome=&reason=&q=&limit=&offset=` serves a step's counts, its reasons
  with counts, and the filtered, paged items.

### When the loader fails the run

A file that cannot be read, for example an empty analysis file, is counted and listed as an error but does not fail
the step, so one bad file no longer stops the dbt rebuild for every other analysis. Before #823 any unreadable file
failed the step and dbt was skipped.

**What to do about "File could not be read".** The file is the saved output of the analysis step, so there is
nothing to download again. It is usually empty because a run was interrupted while writing it. The analysis stage
treats an empty or non-JSON file as not analysed (#825), so the next analysis run for that jurisdiction redoes the
meeting and overwrites the file; then run the load again. The redo is one more paid model call, made only by a run you
start.

The loader exits non-zero, which stops the run before dbt, when:

- a **database write fails**;
- the **cache folder is missing**;
- files were unreadable **and nothing loaded at all** (a broken mount or permissions, not one bad file);
- the run itself raises.

Two cases still finish as "completed" and are worth a look when the counts seem wrong: every file skipped as
`no_event` (no events have been promoted), and a `--tier` run, where files of the other tier are not counted as read.
The counts are written even when the run raises partway, so the tab shows how far it got.

## What the load skips

The load only reads files. It never moves, renames or deletes one, and a skipped file stays where it is. A file is
skipped, and counted by reason, when:

| Reason | Rule |
|---|---|
| `policy_excluded` | the video's transcript was marked `excluded:<reason>` at analysis time (promos, news, non-meetings) |
| `junk_channel` | the channel is classified junk (`bronze_youtube_channel_classification.is_junk`) |
| `non_meeting_type` | `meeting_type` is OTHER, UNKNOWN or blank **and nothing else says it is a meeting** (see below) |
| `low_keep_score` | the Jev keep-score `P(government_meeting) + P(town_hall)` is below `--min-meeting-p` (default 0.6); human overrides to `government_meeting` or `town_hall` win, and unscreened videos are never skipped |
| `no_event` | the video has no promoted `civic_event` row yet (run `ingestion.youtube.promote_to_c1_event`) |
| `no_meta` | the file has no metadata file of its own |
| `meta_mismatch` | its metadata was written for the other tier's analysis file (see below) |

### "Other" is not "not a meeting" (#829)

The scraper types a video from a few words in its title (city council, planning, zoning, school board, special,
workshop) and calls everything else `Other`. Committee meetings, commissions, work sessions and briefings all arrive as
`Other`, so that value alone says little. A video typed OTHER, UNKNOWN or blank is **loaded** when any of these says it
is a meeting, checked in this order:

1. a person marked it `government_meeting` or `town_hall` on the Meeting kinds tab;
2. its Jev keep-score is at or above the floor (`--min-meeting-p`, default 0.6);
3. its title names a public body or a meeting form: council, commission, committee, board, authority, work session,
   briefing, public hearing, town hall, regular or special meeting, and similar.

A person's verdict wins both ways: if someone marked the video as something other than a meeting, the title and the
score are not consulted and it is skipped. A title match does not override the other rules, so a junk channel, an
excluded transcript or a low Jev keep-score still skips it.

The loader's summary line counts how many `Other` videos were kept by each kind of evidence. For one that is still
skipped, the drill-down's detail column shows the stored type and the title, so a real meeting that slipped through
can be spotted and marked on the Meeting kinds tab.

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
way are detected by the loader (the metadata lists the other tier's analysis file) and skipped as `meta_mismatch`,
never paired with the wrong analysis.

Only the tier is compared, not the file name (#820). When a meeting's date or title is corrected, its analysis and
metadata are renamed together and the path stored inside the metadata keeps the old name; that is still the file's
own record, so it loads. Before #820 any name difference was skipped, which dropped 49 renamed analyses in one run.

## The cache repair tool no longer deletes

`transcript_cache_paths._safe_move` (layout migration and basename repair) used to delete the older of two files that
map to the same name. It now moves that file into a `_superseded/` folder next to it, so no analysis is lost. A name
already taken there gets the file's modified time added.

## Still open on #796

- Storing the tier on each analysis in the database for display (a new column). It is tracked with the provenance
  footer in #798.
