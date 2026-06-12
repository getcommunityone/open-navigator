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

> Broader, whole-repo view (duplicated assets, stray entry points, orphaned stacks,
> packaging sprawl, usability) lives in the [Refactor & Tech-Debt Plan](./refactor-plan.md).
> This file stays focused on the `scripts/ → packages/` port (that plan's Theme 6).

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
`test_pipeline_media_scope`) repointed.

**`scripts/utils/gdrive_paths.py` → `core_lib.gdrive_paths`** (2026-06-10): the residual
governance cross-dep is gone. `git mv`-d into `packages/core-lib/src/core_lib/` (blame
preserved), chosen over `packages/llm` because it's a pure-stdlib path util shared by **both**
`llm.governance.*` and `scrapers.wikidata.export_bronze_to_json` (and several `scripts/`) —
`core-lib` is already a dependency of both, so no package gains a heavy `llm` dep. All importers
repointed to `core_lib.gdrive_paths`; `colab_bootstrap` + the notebook §1 bootstrap now add
`packages/core-lib/src` to `sys.path`; legacy `scripts/discovery/*` + `scripts/utils/log_sync.py`
bootstraps add the same. Unit tests under `packages/core-lib/tests/test_gdrive_paths.py`.

**In flight:** `feat/llm-enrichment-extraction` (current branch) — enrichment subpackage port.

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
