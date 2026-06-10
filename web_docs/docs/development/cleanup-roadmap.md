---
title: Cleanup Roadmap
---

# Cleanup Roadmap — Manager's Memory

This is the **Manager surface** for the monorepo refactor: the high-level map of what's
done, what's next, and how to route work. It pairs with two other persistent stores —
keep all three in sync, don't duplicate:

- **`CLAUDE.md`** (repo root) — the standing rules every session/sub-agent must obey.
- **Claude Code memory** (`.claude/.../memory/`) — cross-session facts; the canonical,
  detailed refactor recipe + progress lives in `project_core_lib_refactor.md`.
- **This file** — the living backlog + routing table for the cleanup.

## Goal

Eliminate the top-level `scripts/` tree. Move everything into `packages/` refactored
**correctly as libraries** (not just relocated). Any leftover `scripts/` module is a
porting candidate, not a permanent home.

## Sub-agent routing (the specialists)

The Manager (interactive Claude) holds this roadmap and routes scoped work to isolated
specialists in `.claude/agents/`. Each runs in a clean, narrow context and returns only
a summary — no raw file dumps bleed back.

| Specialist | Owns | Spin up for |
|---|---|---|
| `python-packages-specialist` | the `packages/` uv workspace (accessibility, agents, core, core-lib, datamodels, ingestion, llm, scrapers) | "where should this Python live", porting `scripts/ → packages/`, library refactors. Enforces **prefer packages, never add to scripts/** |
| `data-dbt-specialist` | `dbt_project/`, `scripts/datasources/*`, `scripts/enrichment*`, `scripts/discovery/` | dbt models, SQL/JSONB transformation logic, data semantics |
| `api-specialist` | `api/` (app, routes, models, auth, errors, batch_jobs) | FastAPI routes, Pydantic schemas, API DB access, OTel |
| `frontend-specialist` | `frontend/src/`, `website/` | React/TS components, hooks, API client, Tailwind, Docusaurus |

> Overlap note: Python library *structure / where code lives* → `python-packages-specialist`;
> dbt/SQL transformation *semantics* → `data-dbt-specialist`. A datasource port touches
> both — lead with python-packages for the move, pull in data-dbt for the SQL details.

Route by file scope. A task that crosses layers gets split: the specialist flags
out-of-scope work in its summary and hands it back to the Manager to re-route.

## The established port recipe (summary — full version in memory)

1. Branch off `main`: `feat/datasource-<source>-port`.
2. **Two commits, never one:** first a pure `git mv legacy_loader.py <name>_pipeline.py`
   (so `git blame --follow` survives), then a second commit that refactors contents.
3. Per script: define `<Name>Row(RawRow)` pydantic schema (Field max_length = bronze
   widths); implement `<Source>Pipeline(DataSourcePipeline[<Name>Row])` with
   `extract()` (async stream of validated dicts) + `load_batch()` (parameterized
   `text()` UPSERT, JSONB via `CAST(:col AS jsonb)`); replace psycopg2 / hardcoded
   `DATABASE_URL` with `core_lib.db` (`async_session`, `get_async_engine`). Preserve
   pure helpers and UPSERT ON CONFLICT semantics verbatim. Keep `--file/--limit/--truncate`.
4. Unit tests in `tests/test_<source>_<name>_pipeline.py` (helpers, schema +/-,
   metadata, synthetic-file extract, error paths).
5. **After porting, grep the whole repo for the OLD import path** — exporters/QA/frontend-prep
   scripts silently still import it. Update or list in the PR body.
6. New workspace member ⇒ `uv sync` (or `.venv/bin/pip install -e packages/<new>`).
7. Triage before porting: many "still references old table" scripts are **dead/superseded
   by dbt** — grep usages + check for a dbt replacement before assuming a port; archive
   dead ones to `archive/datasources/<source>/` via `git mv`.

## Status (as of 2026-05-30)

**Done / merged to `main`:** core-lib framework + 6 ports (census/states, fec/contributions,
gsa/domains, hifld/locations, dot/events, uscm/mayors). 16 branches consolidated → just
`main`. `packages/llm` extracted (gemini + enrichment subpackages). Migration-048 cleanup
swept refs to the dropped `public.jurisdiction` table (now `public.civic_jurisdiction`).

**`scripts/colab/` eliminated → `packages/llm/src/llm/governance/`** (2026-05-30): 24 live
modules + notebook + README + mount_drive.sh + 2 CLIs moved via `git mv` (blame preserved);
flat Colab imports rewritten to package-relative (`from .x import …`); dead `colab_public_data.py`
+ `colab_notebook_ui.py` (+ its test) deleted. Notebook bootstrap now adds `packages/llm/src` to
`sys.path` and imports `llm.governance.*`; CLIs run via `python -m llm.governance.<cli>`. Tests
(`test_colab_bootstrap`, `test_colab_runtime_phases`, `test_meeting_consolidated_summary`,
`test_pipeline_media_scope`) repointed. **Residual cross-dep:** governance modules still import
`scripts.utils.gdrive_paths` (shared with `scripts/discovery/*`) — port that util next so the
package stops reaching into `scripts/`.

**`scripts/` dead-code sweep + 5 ports** (2026-06-10, branch `feat/scripts-refactor-cleanup`):
- **Deleted provably-dead/archived code** (16 files, zero importers): `datasources/localview/archive/*`,
  `discovery/archive/*`, `datasources/osf/load_osf_rds_to_bronze.R`, `datasources/hifld/download_and_load_hifld.sh`,
  `datasources/voter_data/*`, the one-off state-naming migrations (`migrations/migrate_state_naming.py`,
  `fix_persons_scraped_jurisdiction_ids.sql`, top-level `migrate_all_*state_naming.py`), and personal-machine
  Cursor scripts.
- **Ported (git mv + all importers re-pointed + tests):**
  - nonprofit-990 enrichers → `scrapers.irs.{enrich_nonprofits_gt990,enrich_nonprofits_bigquery}` (heavy deps
    boto3/bigquery/xmltodict made lazy; fixed broken subprocess paths in `manage_nonprofits.py`).
  - `jurisdiction_id.py` → `core_lib.jurisdictions.jurisdiction_id` (foundational, ~20 importers incl.
    `api/batch_jobs`); resolved an upward layering bug by relocating `slug_snake_case` down to `core_lib.text`.
  - jurisdiction-mapping analysis → `ingestion.jurisdictions.mapping.*` (5 modules + CLI).
  - reusable discovery modules → `scrapers.discovery.*` (8 from `discovery/` + `crawl_llm_sidecar` from
    `scraping/`; ~70 importers re-pointed).
  - clean leaf scrapers → `scrapers.discovery.social_media_discovery`, `scrapers.youtube.{scrape_youtube_channels,
    youtube_channel_enrich}` (removed real packages→scripts violations).
- **Deferred (complex, needs scoping):** the `jurisdiction_pilot` hub — `scrape_priority_states` (~3500L) top-level
  imports ~10 `scripts/discovery` persist/orchestrator KEEP modules (`bronze_*_persist`, `contact_directory_heuristics`,
  `contact_profile_images`, `jurisdiction_contact_seed_urls`, …) plus `ma_pilot.mayor_boost`. Porting it cleanly
  requires porting those discovery modules first. Same for `website_elections` (→ needs `election_extract_from_html`)
  and the `http_fetch`/`mayor_url_discovery`/`county_municipality_websites` sub-web. The two big orchestrators
  (`jurisdiction_discovery_pipeline`, `comprehensive_discovery_pipeline_jurisdiction`) stay in `scripts/` for now.

**In flight:** `feat/llm-enrichment-extraction` — enrichment subpackage port.

**Backlog (prioritized):**
- _Small/clean ports:_ nccs, naco, ballotpedia (measures), nces.
- _Medium (multi-loader):_ census (acs, municipalities…), parcels, jurisdictions, openstates.
- _Complex (need scoping, don't fit DataSourcePipeline cleanly):_ irs/load_irs_bmf.py,
  ballotpedia_integration.py (1570L), google_civic (1147L), wikidata (18 files), youtube (29 files).
- _HTTP downloaders (BaseAsyncClient migration, not DataSourcePipeline):_ download_gsa_domains,
  download_hifld, download_state_dot_public_pages, load_fec_bulk.
- _Skip (not pipelines):_ one-off SQL fixes, demos, helper modules, READMEs.

**Remaining `scripts/` subdirs still to triage:** data, database, datasources,
deployment, discovery, eboard, enrichment, enrichment_ai, examples, frontend, huggingface,
jurisdictions, localview, maintenance, mcp, media, migrations, scraping, utils, wikicommons,
wikimedia. (`colab` ✅ done → `packages/llm/src/llm/governance/`.)

## Context hygiene (native, not hand-rolled)

Claude Code handles compaction and tool-result lifecycle automatically — don't build a
message-pruning wrapper. When a unit of work finishes: record durable facts in memory,
update this roadmap's Status, and start a fresh session for the next module.
