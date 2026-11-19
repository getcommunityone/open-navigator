---
sidebar_position: 33
title: NER, Splink MDM, and Jev roster screening
description: Propose people and places from transcripts with NER, resolve them with Splink, confirm cheaply with Jev.
---

# NER, Splink MDM, and Jev roster screening

Issue [#623](https://github.com/getcommunityone/open-navigator/issues/623). Pilot evidence lives on Drive under
`CommunityOne/open-navigator/crawl/policy_analysis_compare/2026-11-19/comparison/Vs1PKup62NA/` (Hancock Parks
meeting `Vs1PKup62NA`).

## Division of labor

| Step | Who | What |
|---|---|---|
| Propose spans | spaCy NER (or Gemini Part 1) | Person / place / org surface forms from the transcript |
| Land raw rows | Python → **bronze** | Explicit `source_system` (e.g. `spacy_ner`, `gemini-…`); never patch `public` |
| Resolve masters | **Splink** (`ingestion.mdm`) | Same path as AI persons: conform → cluster → `mdm_person` / bridges |
| Confirm on a meeting | **Jev** Noul/Choice | Roster in, probabilities out — does not invent names or dollar digits |
| Full Part 1 JSON | Gemini (or future hybrid) | Decisions with quotes, competing views, schema the site already reads |

Jev alone is not an extractor. With a roster (warehouse or NER), it is a fast screen. Splink is already the MDM
linker ([entity resolution](../dbt/entity-resolution-mdm.md)); do not add a second master-data tool.

## Why this shape

- Gemini Part 1 is accurate but costly. Hancock Parks showed Jev + `public.event_decision` headlines recovering the
  four real decisions from 39 county distractors in ~0.25s, and Jev + Hancock `event_person` recovering all nine
  Gemini people (including two Gemma missed).
- Money uses the same idea with a **regex** roster ([TypeSafe pre-parsed extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md)).
  Names need NER or a prior roster; amounts need `$…` / thousands patterns.
- AI persons already feed MDM from `bronze.bronze_persons_from_ai`. NER candidates should look like that grain so
  Splink does not care who proposed the string.

## Build order

1. **CLI propose + optional Jev confirm** (this change) — `python -m llm.ner.transcript_candidates`. Writes JSON
   under the Drive crawl tree (or `--out`). Does not invent bronze DDL yet.
2. **Bronze table** `bronze_persons_from_ner` / places sibling — same spirit as `bronze_persons_from_ai`, keyed by
   `(video_id or source_event_id, span)`.
3. **dbt** — add the NER source to `int_persons__unioned` (and places when ready).
4. **Splink** — no new linker; run the existing person job after NER loads.
5. **Jev screen** — jurisdiction roster from MDM / event marts + NER newcomers; `--skip-jev-below` stays opt-in until
   calibrated ([Jev screening](./jev-transcript-screening.md)).

## Deliverables path

Per `AGENTS.md`: put pilot outputs under `My Drive/CommunityOne/open-navigator/crawl/…`, not Downloads.
