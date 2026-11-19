---
title: Analysis model preference
sidebar_label: Analysis model preference
---

# Analysis model preference

When more than one AI analysis is loaded for the same meeting video
(`bronze.bronze_events_analysis_ai` is keyed on `(event_id, analysis_type, ai_model)`),
serving tables keep **one** decision set per meeting ([#519](https://github.com/getcommunityone/open-navigator/issues/519)).

## Rule

`int_preferred_event_analysis` picks one analysis id per `event_id`:

1. **Gemini-family** models (`ai_model` contains `gemini`) win over
2. **Gemma** (`ai_model` contains `gemma`), which wins over
3. any other model.

Ties break by newest `created_at`, then highest analysis `id`.

`event_meeting` and `event_decision` only join that preferred analysis, so a
Gemma import for a video that already has Gemini does not add a second meeting
or a second decision set on the site.

## Rebuild note

`event_meeting` / `event_decision` are append-only. After deploying this rule,
rebuild (or prune non-preferred `analysis_id` rows) so older dual loads leave
`public`. New increments only insert the preferred analysis.
