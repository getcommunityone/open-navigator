---
title: Code walkthrough
sidebar_label: Code walkthrough
description: How the code turns public records into what the app shows, step by step in run order, with a link to the code for each step.
format: md
---

# Code walkthrough

**How a public meeting becomes a decision you can search, step by step in run order.** Each step says what it does,
links the code, and gives the command, what it writes and how to check it. Most data steps are package CLIs
(`python -m <package>.<module>`); `scripts/` is legacy and frozen ([cleanup roadmap](./cleanup-roadmap.md)).

The short version: **find governments and their sites → collect meetings and reference data → AI reads the
transcripts → dbt cleans, joins and scores → copy the serving tables to Neon → the API serves them → the app shows
them.**

## The steps in run order

| # | Step | Command (from the repo root) | Writes |
|---|---|---|---|
| 1 | [Find governments and their websites](#1-find-governments-and-their-websites) | `python -m ingestion.census.municipalities` | `bronze` jurisdictions |
| 2 | [Collect meetings](#2-collect-meetings) | `python -m ingestion.youtube.events` | `bronze` meeting videos |
| 3 | [Load reference data](#3-load-reference-data) | `python -m ingestion.irs.bmf` | `bronze` nonprofits, Census, bills |
| 4 | [AI reads the transcripts](#4-ai-reads-the-transcripts) | `python -m llm.gemini.batch_backlog submit --state AL` | `bronze_events_analysis_ai` |
| 5 | [Clean, join and model in dbt](#5-clean-join-and-model-in-dbt) | `cd dbt_project && dbt build` | `staging`, `intermediate`, marts, `public` |
| 6 | [Match the same entity across sources](#6-match-the-same-entity-across-sources) | `python -m ingestion.mdm address` | `bronze` clusters, then dbt |
| 7 | [Policy questions and arguments](#7-policy-questions-and-arguments) | `python -m llm.policy_questions.run_pipeline` | `policy_question`, `canonical_argument` |
| 8 | [Score items for the story lenses](#8-score-items-for-the-story-lenses) | (in step 5's `dbt build`) | `item_interestingness` |
| 9 | [Publish to Neon](#9-publish-to-neon) | `python -m hosting.neon.sync_public_to_neon --dry-run` | Neon `public` |
| 10 | [Serve it: the API](#10-serve-it-the-api) | `python main.py serve --port 8001` | JSON at `/api/...` |
| 11 | [Show it: the web app](#11-show-it-the-web-app) | `cd web_app && npm run dev` | pages at `localhost:5173` |
| 12 | [Deploy](#12-deploy) | GitHub Actions: Deploy to Hugging Face Spaces | communityone.com |

Every loader in steps 1 to 3 follows one contract, `DataSourcePipeline`
([core_lib/pipeline/base.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/core-lib/src/core_lib/pipeline/base.py)):
`extract()` yields raw rows, a Pydantic schema validates them, and `load_batch()` writes them in batches, with
metrics and rollback. Read it once and every loader reads the same way.

## 1. Find governments and their websites

The list of places comes from the Census: Gazetteer places, counties and school districts. Discovery then finds each
government's website, its meeting platform (Legistar, Granicus and others) and its YouTube channel.

- Code: [ingestion/census/](https://github.com/getcommunityone/open-navigator/tree/main/packages/ingestion/src/ingestion/census)
  (`municipalities.py`, `counties.py`, `gazetteer.py`, `shapefiles.py`);
  [scrapers/discovery/](https://github.com/getcommunityone/open-navigator/tree/main/packages/scrapers/src/scrapers/discovery)
  (`platform_detector.py`, `url_discovery_agent.py`, `youtube_channel_verification.py`).
- Writes: jurisdiction rows in `bronze`, with website and channel URLs as they're found.
- Check: the jurisdiction mapping-quality page in the app (`/jurisdiction-quality`) shows which places have a website
  and a channel, and which don't.

## 2. Collect meetings

Meetings arrive from many platforms, so each platform has an adapter that turns its records into one `Meeting`
shape. YouTube is the main source of video and captions.

- Code: [ingestion/meetings/](https://github.com/getcommunityone/open-navigator/tree/main/packages/ingestion/src/ingestion/meetings)
  (`model.py` the shape, `adapters.py` one per platform, `registry.py` `adapter_for()`);
  [ingestion/youtube/events.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/youtube/events.py)
  (lands pre-collected video records into `bronze`);
  [scrapers/discovery/meetings_playwright_fetch.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/scrapers/src/scrapers/discovery/meetings_playwright_fetch.py)
  (agendas and minutes from portals).
- Writes: meeting and video rows in `bronze`.
- Check: `ingestion.meetings.coverage_report` lists which platforms have an adapter.

## 3. Load reference data

The context around a decision: nonprofits from the IRS, demographics and finance from the Census, state bills from
Open States, and more (one folder per source under `ingestion/`).

- Code: [ingestion/irs/bmf.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/irs/bmf.py)
  (IRS Business Master File); [ingestion/census/acs.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/census/acs.py);
  [ingestion/openstates/](https://github.com/getcommunityone/open-navigator/tree/main/packages/ingestion/src/ingestion/openstates).
- Writes: `bronze` tables, one per source.
- Check: each source's licence and citation is in [CITATIONS.md](https://github.com/getcommunityone/open-navigator/blob/main/CITATIONS.md);
  adding a source: [adding data sources](./adding-data-sources.md).

## 4. AI reads the transcripts

Gemini reads each meeting transcript with a fixed prompt and returns structured JSON: the decisions made, how each
member voted, who spoke, and the quote for each. Batch mode sends the backlog as one file, answered within a day at
a lower price.

- Code: [llm/gemini/meeting_transcript_policy.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/meeting_transcript_policy.py)
  (one transcript); [analyze_backlog.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/analyze_backlog.py)
  (one call at a time); [batch_backlog.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/batch_backlog.py)
  (submit, poll, collect). The prompt:
  [prompts/policy_analysis_part_1.md](https://github.com/getcommunityone/open-navigator/blob/main/prompts/policy_analysis_part_1.md).
- Cost: every call is logged by [llm/usage/](https://github.com/getcommunityone/open-navigator/tree/main/packages/llm/src/llm/usage)
  and rolled up in the `llm_usage_daily` mart ([LLM usage tracking](./llm-usage-tracking.md)).
- Writes: `bronze.bronze_events_analysis_ai`.
- Check: `python -m llm.gemini.batch_backlog` has `status` and `collect` steps; each is safe to re-run.

## 5. Clean, join and model in dbt

Every SQL transformation is dbt, never Python. Four layers: **bronze** (as landed) → **staging** (typed and renamed,
years cast to integers) → **intermediate** (joined and enriched) → **marts** (what the app reads). Today that is
16 bronze, 71 staging, 55 intermediate and 102 mart models. The marts the API serves are published as views in
`public`, each with a declared primary key and foreign keys.

- Code: [dbt_project/models/](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/models). One
  decision, as an example:
  [marts/event_decision.sql](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/event_decision.sql)
  reads `bronze_events_analysis_ai` and `bronze_decisions_from_ai` and joins them to `event_meeting`.
- Run: `cd dbt_project && dbt build` (models and tests). Before changing a model, list what depends on it:
  `dbt ls --select <model>+`.
- Check: `dbt test`; the contracts in [data contracts](./data-contracts.md); the diagrams in
  [data model](../data-sources/data-model-erd.md).

## 6. Match the same entity across sources

The same person, address or nonprofit shows up in several sources under slightly different names. dbt builds the
pooled inputs, Splink predicts which records are the same entity and clusters them, and dbt serves the result.

- Code: [ingestion/mdm/](https://github.com/getcommunityone/open-navigator/tree/main/packages/ingestion/src/ingestion/mdm).
- Run: `python -m ingestion.mdm address`, `python -m ingestion.mdm person --dry-run`.
- Writes: cluster tables in `bronze`, served by the `mdm_*` marts.
- Read: [entity resolution](../dbt/entity-resolution-mdm.md), [bronze to production merge](./bronze-to-production-merge.md).

## 7. Policy questions and arguments

Turns one-off votes into questions that recur across places. Decisions are embedded and clustered into
place-neutral **policy questions**, and the arguments made for and against are clustered into a **canonical argument**
library (the Key Point Analysis method), each tagged with a frame from the Policy Frames Codebook.

- Code: [llm/policy_questions/](https://github.com/getcommunityone/open-navigator/tree/main/packages/llm/src/llm/policy_questions)
  (`embed_instances.py`, `cluster_questions.py`, `cluster_arguments.py`, `labeler.py`, `run_pipeline.py`).
- Run: `python -m llm.policy_questions.run_pipeline` (no AI calls, for checking); add `--use-llm` for a real labelled
  run, which is billed.
- Writes: `policy_question`, `canonical_argument`, `question_instance`, `instance_argument` marts.
- Serves: `/api/policy-question` ([policy_questions.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/policy_questions.py)).

## 8. Score items for the story lenses

Each decision and meeting item gets signals (split votes, money moved, unusual patterns, speed, upcoming dates),
normalised and combined into a score. The five lenses on the home page (Contested, Money Moves, Raised Eyebrows,
Moving Fast, Watch Next) are views over that score.

- Code: [intermediate/int_civic__item_signals.sql](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/intermediate/int_civic__item_signals.sql)
  → [marts/item_interestingness.sql](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/item_interestingness.sql);
  unusual-pattern flags in [marts/item_flags.sql](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/item_flags.sql).
- Serves: `/api/lenses` ([lenses.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/lenses.py)), which only reads the
  table: no scoring in the API.
- The home page asks for `window=auto` until the reader picks a period. The API returns the narrowest window that has
  decisions for the place, and its chip is highlighted. A place whose newest analysed decision is months old, such as
  Alabama (newest 2026-06-10), opens on **Past year**, not an empty **Past month**
  ([#1045](https://github.com/getcommunityone/open-navigator/issues/1045)).

## 9. Publish to Neon

The warehouse runs locally (Postgres on `localhost:5433`). Production reads Neon, a hosted Postgres. This step copies
the built `public` serving objects to Neon as plain tables; it doesn't run dbt there.

- Code: [hosting/neon/sync_public_to_neon.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/hosting/src/hosting/neon/sync_public_to_neon.py).
- Run: `python -m hosting.neon.sync_public_to_neon --dry-run` first, then without it (prod) or with `--target dev`.
  `--only <table> ...` copies a subset.
- Needs: `NEON_DATABASE_URL` (prod) or `NEON_DATABASE_URL_DEV` in `.env`.
- Read: [Neon deployment](../deployment/neon-deployment.md).

## 10. Serve it: the API

FastAPI, one router per feature under `api/routes/`. Routes read the `public` schema and do no transformation. The
database is the first of `NEON_DATABASE_URL_DEV`, `NEON_DATABASE_URL`, `DATABASE_URL` that is set
([api/database.py](https://github.com/getcommunityone/open-navigator/blob/main/api/database.py)).

| Route | File | Reads |
|---|---|---|
| `/api/search` | [search.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/search.py), queries in [search_postgres.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/search_postgres.py) | search tables; `ts_headline` builds the highlighted passage for each result |
| `/api/decision/{id}` | [decisions.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/decisions.py) | `event_decision` |
| `/api/lenses` | [lenses.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/lenses.py) | `item_interestingness` |
| `/api/policy-question` | [policy_questions.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/policy_questions.py) | `policy_question` and its arguments |
| `/api/money-and-talk` | [money_and_talk.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/money_and_talk.py) | `topic_money_and_talk` |
| `/api/stats` | [stats_neon.py](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/stats_neon.py) | `jurisdiction_state_aggregate` |

- Start: [api/main.py](https://github.com/getcommunityone/open-navigator/blob/main/api/main.py) registers the routers;
  `./start-all.sh` runs it on port 8001 with the app and docs.
- Check: `http://localhost:8001/docs` lists every route. The app's TypeScript types are generated from the OpenAPI
  schema (`web_app/src/lib/api.types.ts`), and CI checks they're current.

## 11. Show it: the web app

React, Vite and TypeScript. Two rules shape every page that filters data: the scope label always names the filter
actually applied, carried in the URL (`?state=&city=`), and a result found by a search term shows the passage that
matched, highlighted.

- Scope label, the reference pattern: [BrowseTopics.tsx](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/pages/BrowseTopics.tsx)
  and [DecisionCardList.tsx](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/components/DecisionCardList.tsx).
- Matched passage: [UnifiedSearch.tsx](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/pages/UnifiedSearch.tsx)
  renders the API's `<mark>` snippet through [lib/highlight.tsx](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/lib/highlight.tsx),
  escaped, never as raw HTML.
- Lenses: [StoryLenses.tsx](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/components/StoryLenses.tsx).
- API calls: [lib/apiClient.ts](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/lib/apiClient.ts) and
  `web_app/src/api/`. Routes are in `web_app/src/App.tsx`.

## 12. Deploy

Production is one Docker container on Hugging Face Spaces. nginx serves the built app at `/` and the docs at
`/docs/`, and passes `/api/` to uvicorn on port 8000; supervisord keeps both running.

- Code: [Dockerfile.huggingface](https://github.com/getcommunityone/open-navigator/blob/main/Dockerfile.huggingface),
  [.huggingface/nginx.conf](https://github.com/getcommunityone/open-navigator/blob/main/.huggingface/nginx.conf),
  [.huggingface/supervisord.conf](https://github.com/getcommunityone/open-navigator/blob/main/.huggingface/supervisord.conf),
  the workflow [deploy-huggingface.yml](https://github.com/getcommunityone/open-navigator/blob/main/.github/workflows/deploy-huggingface.yml),
  and helpers in [hosting/huggingface/spaces.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/hosting/src/hosting/huggingface/spaces.py).
- If the site shows **502 Bad Gateway from nginx**, nginx is up but uvicorn isn't answering: open the Space's
  container logs and look for the first traceback from `api.main`, often a database connection error.
- Read: [Hugging Face Spaces](../deployment/huggingface-spaces.md).

## Where to change things

| To change | Start in |
|---|---|
| A new data source | a folder under `packages/ingestion/src/ingestion/`, on the `DataSourcePipeline` contract |
| What the AI extracts from a transcript | `prompts/policy_analysis_part_1.md`, then step 5's bronze models |
| A number or list the app shows | its mart in `dbt_project/models/marts/`, never the API |
| A new API endpoint | a router in `api/routes/`, registered in `api/main.py`; regenerate `api.types.ts` |
| A page | `web_app/src/pages/`, following the scope-label and matched-passage rules in `CLAUDE.md` |
| The rules themselves | `CLAUDE.md` and `AGENTS.md` |
