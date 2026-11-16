---
sidebar_position: 6
title: Context engineering
description: The six principles for what an AI model in Open Navigator is allowed to see and must know, and where each one applies in this repository.
---

# Context engineering

Prompt engineering shapes the instruction: how the model should phrase its answer. Context engineering designs
everything the model works from: what it must know to answer correctly, and whether it's allowed to know it.

Open Navigator puts a lot in front of models. Gemini reads meeting transcripts and writes the decisions, quotes and
dollar amounts the site shows. Jev screens transcripts. Coding agents read this repository. In each case the context is
an engineering asset: governed, versioned and tested, not whatever happens to land in the window.

The six principles below each say where the repository already follows them and where it falls short. When you add a
model call, a prompt, an agent or a data feed for one, check it against all six.

## In short

| Principle | The rule | Where it matters most here |
|---|---|---|
| 1. Relevance and minimalism | Send the smallest context that answers the question | Transcript analysis, Jev screening, coding agents |
| 2. Governance and access control | Access rules belong to the data, not to the prompt | `gold` / `public` split, Neon copy, Unity Catalog |
| 3. Structural integrity and ontology | Context carries business meaning, not just column names | dbt schema files, MDM graph, policy-question registry |
| 4. Provenance and traceability | Every derived row or quote links back to its source | Quoted evidence on tiles, source and licence on records |
| 5. Temporal state and freshness | The model and the reader can tell how current the data is | Last-seen dates, verified-at dates, stale tables |
| 6. Deterministic evaluation | Context is tested like code, not judged by feel | Prompts in git, usage log, model comparisons |

## 1. Relevance and minimalism

More context isn't better context. A huge window full of loosely related text lowers retrieval accuracy, and
conflicting definitions in it confuse the model.

- **Semantic chunking:** split documents at units of meaning (a caption segment, a Markdown section, a JSON object),
  not at an arbitrary character count.
- **Just-in-time over up-front:** give the model light references and a tool to load detail when it needs it, rather
  than loading everything at the start.

<details>
<summary>Where this applies</summary>

| Where | What it does now |
|---|---|
| Transcript analysis, `prompts/policy_analysis_part_1.md` (about 35 KB) | The fixed prompt comes first and the per-meeting block last, so calls share a prefix and Gemini's implicit cache applies. See [Transcript analysis cost](./transcript-analysis-cost.md) |
| Transcript source, `packages/llm/src/llm/gemini/transcript_db.py` | Reads timed caption segments from `bronze_event_youtube_transcript`, keeping segment boundaries and timestamps instead of one flat blob |
| Jev screening (proposed, branch `feat/jev-transcript-screening`) | Cuts transcripts at caption-segment boundaries into chunks under Jev's 32k-token per-question limit, and screens a few evenly spaced chunks instead of switching on the slower, less accurate long-context mode |
| Coding agents, `CLAUDE.md` and `.claude/agents/` | Agents are told not to read raw data files, logs or parquet dumps, and to read schemas instead. Scoped work goes to specialist agents, each with a narrow brief |

**Gaps**
- The analysis prompt is one large block for every meeting, whatever its length or type. A short ceremony gets the
  same 35 KB of instructions as a three-hour budget hearing.
- Long transcripts are sent whole. Nothing selects the parts of a meeting that hold decisions before analysis.

</details>

## 2. Governance and access control

If access rules live in an agent's prompt, every new agent is a fresh chance to leak data. Privacy, role-based access
and licensing must be properties of the data the model can reach.

- **Access attached to the data:** a model should only be able to read what the calling user may see, because the
  layer it reads from enforces that, not because the prompt asks nicely.
- **One governance layer:** filter sensitive or regulated data before it reaches the model's context or a vector index.

<details>
<summary>Where this applies</summary>

| Where | What it does now |
|---|---|
| `gold` / `public` schema split, `dbt_project/macros/publish_public_serving.sql` | `gold` holds the full warehouse. `public` holds only serving views, with a PII-light projection of `contact_official` and `person_government`. The public API reads `public` (`API_DB_SCHEMA`, `api/database.py`) |
| Neon copy, `packages/hosting/src/hosting/neon/sync_public_to_neon.py` | Copies an allow-list of `public` tables to production. Runtime-owned tables such as `job_application_link` are never copied. See [Neon serving scope](./neon-serving-scope.md) |
| Usage log, `packages/llm/src/llm/usage/calls.py` | Only the labels in `CONTEXT_LABELS` (stage, video, jurisdiction, API mode) can be logged, so a transcript or prompt can never end up in the usage log |
| Databricks, `apps/lakebase-serving-sync/` and `apps/agent-analysis-sync/` | Source tables live in Unity Catalog, which is where access control belongs when analysis runs there |
| Licensing, [Data center sites](./data-center-sites.md) | Epoch AI rows carry their CC BY 4.0 credit. Sources whose terms forbid scraping (the Brockovich map) are kept out entirely |

**Gaps**
- Agents and scripts with a warehouse connection string can read `gold` and `bronze`. The rule to use `public` is
  written in `CLAUDE.md`, which is a prompt, not a control. A read-only role limited to `public` would make it a
  property of the data.
- The legacy MCP server, `scripts/mcp/open_navigator_server.py`, should be checked for which schema it reads before
  any agent uses it.

</details>

## 3. Structural integrity and ontology

A raw staging table and a production view can look identical to a model that reads only the schema. Context must
carry the business meaning: definitions, approved formulas, and what's deprecated.

- **Business semantics:** definitions, metric formulas and deprecation tags travel with the data.
- **Relationships as a graph:** people, organizations, places and policies are connected. Let the model follow those
  links rather than relying only on text similarity.

<details>
<summary>Where this applies</summary>

| Where | What it does now |
|---|---|
| dbt `schema.yml` files in `dbt_project/models/` | Model and column descriptions, plus primary and foreign keys on every `public` model, enforced in Postgres |
| Naming rules in `CLAUDE.md` | `state_code` and `state` both present, `website_url` as the web column, entity names rather than `dim_`/`fact_`, bare years stored as integers |
| Medallion layers | `bronze → staging → intermediate → marts`. Only marts published to `public` are meant for the API or a model |
| Shared definitions as macros, e.g. `dbt_project/macros/normalize_coarse_theme.sql` | One definition of a theme, used by every model that needs it |
| Relationship graph | `mdm_person`, `mdm_organization` and the `mdm_bridge_*` tables connect people, organizations, addresses and events. `tag` and `tag_closure` hold the cause hierarchy |
| Policy-question registry, `packages/llm/src/llm/policy_questions/` | Decisions linked to questions, arguments and frames |

**Gaps**
- Nothing marks a model as deprecated. Old and new models that answer the same question look equally valid.
- Metric definitions live in SQL and descriptions, not in a form an agent can look up. `governments_count` and
  `jurisdictions_count` sit side by side; only the column description says that one counts local governments and the
  other Census geographies.

</details>

## 4. Provenance and traceability

Every derived row, chunk or quote carries its source IDs forward through the pipeline, so an answer can be traced back
to the record it came from.

- **Deterministic citations:** an answer points to the authoritative source, by ID and link.
- **Lineage:** an AI output can be audited from the model's answer back to the raw source.

<details>
<summary>Where this applies</summary>

| Where | What it does now |
|---|---|
| No Fabricated Data, `CLAUDE.md` | Every figure shown must trace to a real value. Missing data shows as unavailable, never as a stand-in number |
| Match evidence, `api/routes/search_postgres.py` and `web_app/src/lib/highlight.tsx` | A filtered tile shows a verbatim passage with the matched words highlighted (`ts_headline` in SQL, rendered by `highlightSnippet`), never a paraphrase |
| Bronze loaders | Raw rows keep their source file and row (for example the Epoch tables' primary key is `file_sha256, row_number`) |
| Data center agenda items | Each item carries its `document_url` and the quoted evidence from the agenda |
| dbt lineage | `dbt ls --select <model>+` and the docs graph show every model downstream of a source |

**Gaps**
- `bronze_events_analysis_ai` records `ai_model` and `prompt_version`, but `prompt_version` is a fixed label: all
  7,108 rows say `v1.0` (November 16, 2026), though the prompt has changed many times. It should be derived from the
  prompt file itself (for example a content hash), so each row shows which wording produced it.

</details>

## 5. Temporal state and freshness

Data ages, and a model needs to know what era of data it's looking at. Context needs a freshness target, and the model
and the reader need signs of completeness and staleness.

- **Freshness targets:** policies can refresh monthly; operational data needs live queries or regularly rebuilt views.
- **Staleness indicators:** last-updated dates, last-seen dates and coverage counts travel with the data.

<details>
<summary>Where this applies</summary>

| Where | What it does now |
|---|---|
| Data center sites | First and last seen per site, `is_listed`, and a site the source drops stays visible as "no longer listed" with its last-seen date |
| Job application links | `verified_at`, and a link not checked for 30 days is marked stale. See [Data center application links](./data-center-application-links.md) |
| National stats, `jurisdiction_state_aggregate` | Carries `last_updated`. `/api/stats` caches for 5 minutes |
| Analysis stamps | `policy_analysis_at` on each video says when it was analyzed |

**Gaps, found on November 16, 2026**
- `public.event_documents`, which search reads for transcripts, was last rebuilt on June 14.
- `intermediate.int_events_channels`, the verified channel list the crawl reads, was last loaded on May 27.
- The homepage scrape saved no video links for any of 6,407 city sites, and nothing reported it.
- The local `jurisdiction_state_aggregate` row reported 0 jurisdictions until it was rebuilt.

None of these was flagged by the pipeline. Each table a model or the site reads should have a freshness target and a
check that fails loudly when it's missed.

</details>

## 6. Deterministic evaluation

Asking a bigger model whether an answer looks right is a paid opinion, not a test. Context quality is measured by
recording exactly what entered the window, and by testing against known answers.

- **Trace every run:** which inputs entered the context, when, and why.
- **Prompts as code:** prompts, output schemas and tool definitions live in version control, carry versions, and are
  tested against a golden dataset for groundedness and schema conformity.

<details>
<summary>Where this applies</summary>

| Where | What it does now |
|---|---|
| Prompts in git, `prompts/` | The analysis prompt is versioned with the code that uses it |
| Output schema | Part 1 requests JSON output. `packages/llm/tests/test_part1_field_sizes.py` checks the fields |
| Usage log, `packages/llm/src/llm/usage/` | One row per model call: model, tokens, latency, attempts, success, run ID. `python -m llm.usage.report` prices them. See [LLM usage tracking](./llm-usage-tracking.md) |
| Model comparison, `packages/llm/src/llm/gemini/compare_models.py` | Runs the same transcripts through several models side by side. See [AI model evaluation](./ai-model-evaluation.md) |
| MLflow, `packages/agents/agents/mlflow_base.py` | The agents package logs models with MLflow |
| Jev screening (proposed) | Each screen records a hash of its exact question wording, so a reworded question is rescreened, never mixed with old answers |

**Gaps**
- There is no golden dataset for transcript analysis: a fixed set of meetings with checked decisions, quotes and
  amounts to score each prompt or model change against.
- The usage log records that a call happened, not which prompt version and input it used, and the analysis rows'
  `prompt_version` never changes (see principle 4). Tracing each analysis run (for example with MLflow) would close
  that.
- Decisions about model or threshold changes (such as Jev's skip threshold) should be made from a scored sample, and
  the score recorded with the decision.

</details>

## Checklist for a new model call, prompt or agent

1. **Relevance:** what's the smallest context that answers this? Can detail load on demand instead?
2. **Governance:** which schema or catalog does it read, and does that layer enforce who may see what?
3. **Ontology:** does the context say what each field means, and which models are current?
4. **Provenance:** does every output carry the source ID and link it came from?
5. **Freshness:** does the context say how current it is, and what happens when it's stale?
6. **Evaluation:** is the prompt in git with a version, and is there a test with known answers?
