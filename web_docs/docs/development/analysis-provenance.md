---
title: How a summary was made (provenance)
sidebar_label: Summary provenance
---

# How a summary was made (#798)

The bottom of a decision page has a quiet line, "AI-assisted summary · details". It opens a panel of **recorded facts only**:
model, when it was generated, light or full analysis, prompt name and version, the transcript source, and a link to the
source recording. A fact the run did not record is left out, never filled in. The panel also says the summary is
machine-generated and should be checked against the recording, and says so when the meeting had several analyses and this
one was chosen (see [analysis model preference](./analysis-model-preference.md)).

## Where each fact comes from

| Fact | Stored in | Recorded since |
|---|---|---|
| Model | `bronze_events_analysis_ai.ai_model` | always |
| Generated | `bronze_events_analysis_ai.created_at` | always |
| Light or full | `bronze_events_analysis_ai.analysis_tier` (new, migration 115), from the run metadata `analysis_tier` | the next load; older rows stay empty |
| Prompt name and version | `prompt_version` = `<name>@<first 12 hex of SHA-256>` | rows loaded after #511; the old constant `v1.0` and `@unrecorded` give no prompt |
| Transcript source | `bronze_events_analysis_ai.transcript_source` (new), from the run metadata `transcript.source` | the next analysis run; older rows stay empty |
| Chosen among several | `int_preferred_event_analysis` | always |

`load_analysis_cache_to_bronze` writes the two new columns (and adds them with `ADD COLUMN IF NOT EXISTS` when a database
predates migration `115_add_analysis_provenance_columns.sql`). Existing rows are not backfilled with guesses.

## Model and API

dbt model `event_analysis_provenance` (gold, served in `public`): one row per publishable analysis, primary key
`analysis_id` (= `bronze_events_analysis_ai.id`; `event_decision.analysis_id` for the shown analysis). Columns: `legacy_event_id`,
`video_id`, `state_code`, `ai_model`, `generated_at`, `analysis_tier`, `prompt_name`, `prompt_sha`, `transcript_source`,
`is_preferred`, `analyses_for_meeting`. It also holds the analyses that were not chosen, so it has no foreign key to `event_meeting`.

`GET /api/decisions/{id}` returns `provenance: {model, generated_at, tier, prompt_name, prompt_version, transcript_source,
video_url, analyses_for_meeting}`; every field is nullable and the whole object is null when nothing was recorded. A failed
lookup never fails the decision.

UI: `web_app/src/components/AnalysisProvenance.tsx`. Tests: `tests/test_provenance_798.py`,
`web_app/src/components/AnalysisProvenance.test.ts`.
