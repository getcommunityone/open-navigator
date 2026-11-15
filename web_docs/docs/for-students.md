---
title: For students
sidebar_label: For students
description: Learn AI, classic machine learning, LLMs, dbt, Databricks, MLOps, GitHub Actions, ontologies, data contracts and data products from a real open-source civic data platform, with a code walkthrough for each.
format: md
---

# For students

**Learn AI and data engineering from a real system, not a toy one.** Open Navigator reads public records from local
governments, so every example here runs against real, messy data, and its code shows the trade-offs people make in
practice. Each topic gives you the idea in plain words, the code to read, why it's built that way, and something to
try. Pick any topic; they don't depend on each other.

| Topic | What you'll learn | Start reading |
|---|---|---|
| [1. Basic statistics](#1-basic-statistics) | Median vs mean, percentiles, outliers, minimum sample sizes, precision and recall | [`jurisdiction_minutes_publish_lag.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/jurisdiction_minutes_publish_lag.sql) |
| [2. dbt and the medallion layers](#2-dbt-and-the-medallion-layers) | SQL transformations in layers, tests, seeds, macros | [`dbt_project/models/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/models) |
| [3. Master data management](#3-master-data-management) | One record per real-world person or place; entity resolution with Splink | [`mdm/linker.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/mdm/linker.py) |
| [4. Logistic regression](#4-logistic-regression) | Log-odds, the logistic function, odds ratios, and how Splink uses the same math | [`mdm/settings.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/mdm/settings.py) |
| [5. Classic ML: clustering](#5-classic-ml-clustering) | HDBSCAN, noise, centroids, TF-IDF + SVD | [`policy_questions/cluster.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/cluster.py) |
| [6. Embeddings and retrieval (RAG)](#6-embeddings-and-retrieval-rag) | Sentence embeddings, cosine similarity, pgvector search | [`policy_questions/encoder.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/encoder.py) |
| [7. LLMs in a pipeline](#7-llms-in-a-pipeline) | Prompted extraction, grounding, LLM-as-judge, triage | [`meeting_transcript_policy.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/meeting_transcript_policy.py) |
| [8. Databricks](#8-databricks) | `ai_query` batch inference in dbt, Unity Catalog, Lakebase, asset bundles | [`apps/agent-analysis-sync/`](https://github.com/getcommunityone/open-navigator/tree/main/apps/agent-analysis-sync) |
| [9. MLOps and LLMOps](#9-mlops-and-llmops) | MLflow tracing, usage and cost records, GPU runs, evaluation | [`llm/usage/`](https://github.com/getcommunityone/open-navigator/tree/main/packages/llm/src/llm/usage) |
| [10. GitHub Actions](#10-github-actions) | CI checks, a custom PR check, deploys, on-demand GPU jobs | [`.github/workflows/`](https://github.com/getcommunityone/open-navigator/tree/main/.github/workflows) |
| [11. Ontologies and taxonomies](#11-ontologies-and-taxonomies) | Hierarchies, closure tables, controlled vocabularies | [`int_tags__closure.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/intermediate/int_tags__closure.sql) |
| [12. Data contracts](#12-data-contracts) | Promising a table's shape to its users, checked in CI | [`dbt_project/contracts/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/contracts) |
| [13. Data products](#13-data-products) | Packaging tables, contracts and owners as one product | [`open-navigator-public-api.odps.yaml`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/contracts/products/open-navigator-public-api.odps.yaml) |

**Before you start:** the [quick start](./quickstart.md) sets up the repo. The [code walkthrough](./development/code-walkthrough.md)
shows how the pieces connect in run order, and the [DataOps walkthrough](./development/dataops-walkthrough.md) covers
retries, recovery and data quality. Some commands need the local warehouse or API keys; reading the code needs neither.

## 1. Basic statistics

<details>
<summary><b>Summarise data honestly: the right average, the spread, and when not to publish a number</b></summary>

**The idea.** Before any model, you need to describe data well:
- **mean vs median:** one huge value drags the mean; the median (the middle value) doesn't move, so it's the safer
  "typical" figure for skewed data like delays or dollar amounts;
- **percentiles:** the 90th percentile (p90) is the value 90% of the data falls below, a good "bad case";
- **outliers:** impossible values (a negative delay) are errors to filter, not data to average;
- **sample size:** an estimate from 3 data points is noise; set a minimum and say "not enough data" below it;
- **log transforms:** squash wide-ranging numbers (a $5K and a $5M contract) so they can be compared;
- **precision and recall:** of the things a model found, how many were right (precision); of the things it should have
  found, how many it found (recall).

**Read:**
- [`jurisdiction_minutes_publish_lag.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/jurisdiction_minutes_publish_lag.sql):
  how many days a city takes to publish meeting minutes. It uses the median and p90 (`percentile_cont`) as well as the
  mean, drops lags outside 0–180 days as errors, and publishes nothing for a city with fewer than 5 samples. The API
  then shows "no estimate" instead of a noisy number;
- [`int_civic__item_signal_norms.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/intermediate/int_civic__item_signal_norms.sql):
  percentile ranks within a peer group (cities of a similar size, over a trailing 12 months), with dollar amounts
  log-compressed first (`ln(1+|x|)`) so a $50K item in a small town still ranks high among its peers;
- [`opportunity_atlas_mobility.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/opportunity_atlas_mobility.sql):
  income-rank percentiles from the Opportunity Atlas, shown in the money game's "grandkids" view;
- [`compare_models.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/compare_models.py): recall, precision and
  agreement when comparing two AI models' extractions against a reference. It reports a dash, not a zero, when there
  was nothing to compare.

**Why this way.** The repo's "no fabricated data" rule extends to statistics: a figure from too little data is
treated as missing.

**Try it:** in the warehouse, `select median_lag_days, p90_lag_days, sample_n from public.jurisdiction_minutes_publish_lag
order by sample_n desc limit 10;` and compare each median with its p90.

</details>

## 2. dbt and the medallion layers

<details>
<summary><b>Turn raw data into trustworthy tables, one layer at a time</b></summary>

**The idea.** Raw data lands untouched in **bronze**. **Staging** cleans and renames it, one model per source.
**Intermediate** joins and reshapes. **Marts** are the finished tables the app reads. dbt runs the SQL in dependency
order and tests the results. The repo rule is that every transformation lives in dbt, not Python.

**Read:**
- the layers: [`staging/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/models/staging),
  [`intermediate/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/models/intermediate),
  [`marts/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/models/marts);
- a small staging model: [`stg_acs_property_tax.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/staging/stg_acs_property_tax.sql)
  (it also shows Jinja checking whether a column exists before reading it);
- custom tests that return the rows breaking a rule:
  [`dbt_project/tests/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/tests);
- seeds (small reference CSVs version-controlled with the code):
  [`dbt_project/seeds/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/seeds);
- macros (reusable SQL): [`dbt_project/macros/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/macros).

**Why this way.** Layers make each step small enough to test, and a broken source stops at staging instead of
reaching the app.

**Try it:** `cd dbt_project && dbt ls --select jurisdiction_property_tax_rate+` lists the model and everything
downstream of it, which is what you check before changing a model. More: [dbt overview](./dbt/overview.md),
[conventions](./dbt/conventions.md).

</details>

## 3. Master data management

<details>
<summary><b>One trusted record per real person, organisation and address, built with Splink</b></summary>

**The idea.** **Master data management (MDM)** keeps one "golden" record for each real-world thing, even when ten
systems describe it differently. The same person appears in IRS filings, meeting minutes and official rosters with
different spellings, so MDM works in steps:
- **conform:** standardise the inputs;
- **resolve:** decide which records are the same entity (entity resolution);
- **survive:** pick the best value for each field into the golden record (survivorship).

This repo resolves entities with **Splink**, a classic machine-learning library that implements the Fellegi–Sunter
model:
- **m** is the chance a field agrees when two records really match;
- **u** is the chance it agrees by coincidence;
- **blocking** limits comparisons to plausible pairs, so you don't compare everyone with everyone.

**Read:**
- [`mdm/linker.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/mdm/linker.py):
  the five steps (estimate *u* by random sampling, estimate *m* with expectation maximisation, predict pairs above a
  threshold, cluster, write back);
- [`mdm/settings.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/mdm/settings.py):
  blocking rules run in sequence (so a typo in one field is caught by another) and comparison levels;
- feature engineering in SQL: [`name_phonetic_key.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/macros/name_phonetic_key.sql),
  [`address_match_key.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/macros/address_match_key.sql);
- a test that catches a bad model: [`assert_mdm_person_not_overmerged.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/tests/assert_mdm_person_not_overmerged.sql).

**Why this way.** There are no labelled "true match" pairs to train on. Fellegi–Sunter estimates its parameters from
the data itself (unsupervised), and the person pool is kept separate from organisations so a person never links to an
LLC.

Survivorship (choosing the golden record's values) happens downstream in dbt, not in Splink; the linker's docstring
says where each layer lives.

**Try it:** `python -m ingestion.mdm person --dry-run`. More: [entity resolution and MDM](./dbt/entity-resolution-mdm.md).

</details>

## 4. Logistic regression

<details>
<summary><b>Turn evidence into a probability: log-odds, the logistic function, and odds ratios</b></summary>

**The idea.** Logistic regression predicts a yes/no outcome (match or not, spam or not) as a probability:
- each piece of evidence adds or subtracts **log-odds**;
- the total goes through the **logistic function**, `p = 1 / (1 + e^-z)`, which squashes any number into 0–1;
- each coefficient, exponentiated, is an **odds ratio**: how much that feature multiplies the odds.

Normally you fit the coefficients to labelled examples.

**See the same math in this repo.** Splink's Fellegi–Sunter scoring ([topic 3](#3-master-data-management)) works the
same way:
- each compared field adds a **match weight**: the log (base 2) of how much more likely that agreement is for a true
  match than by chance;
- the weights add up with a prior to a total `w`;
- the total becomes a probability with the logistic function in base 2: `match_probability = 2^w / (1 + 2^w)`.

The difference: Splink sets its weights **without labels**, estimating *m* and *u* by expectation maximisation,
whereas logistic regression **learns** them from labelled data.

**Read:**
- [`mdm/settings.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/mdm/settings.py): the fields compared and their
  levels (exact, close, different), each of which gets its own weight;
- [`mdm/linker.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/mdm/linker.py): where predictions above a
  probability threshold are kept, with `match_probability` and `match_weight` written out for each pair.

**Not built yet: a trained logistic regression.** The repo doesn't have one, so it's a good first contribution: fit
scikit-learn's `LogisticRegression` on real data here, report odds ratios and test-set precision, recall and ROC AUC
([#373](https://github.com/getcommunityone/open-navigator/issues/373), labelled `good first issue`).

</details>

## 5. Classic ML: clustering

<details>
<summary><b>Group similar decisions into recurring policy questions without knowing how many there are</b></summary>

**The idea.** Thousands of local decisions repeat the same few questions ("Should we add fluoride?"). Clustering groups
them. **HDBSCAN** finds clusters of varying density and doesn't need the number of clusters up front. It also puts
one-off items in a **noise** bucket (label `-1`) instead of forcing them into a fake "misc" cluster.

**Read:**
- [`policy_questions/cluster.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/cluster.py):
  HDBSCAN over unit vectors, centroids and exemplars (the members closest to the centre);
- [`policy_questions/encoder.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/encoder.py):
  the fallback when the neural model can't load, TF-IDF (word weights) plus SVD (compressing them to a few dimensions);
- [`cluster_bills.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/cluster_bills.py):
  the same method applied to state bills.

**Why this way.** The number of question families is unknown, and a wrong forced grouping would mislead readers, so a
method with an honest "doesn't fit" answer wins.

**Try it:** `python -m llm.policy_questions.run_pipeline` runs the pipeline without any AI calls, for checking.

</details>

## 6. Embeddings and retrieval (RAG)

<details>
<summary><b>Turn text into vectors so "similar meaning" becomes "close together"</b></summary>

**The idea.** An embedding model maps a sentence to a vector, and similar meanings land close together. After
normalising each vector to length 1, cosine similarity is just a dot product. **RAG** (retrieval-augmented
generation) finds the closest documents and hands them to an LLM, so its answer rests on real sources.

**Read:**
- [`encoder.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/encoder.py):
  the MiniLM model run directly through `transformers` (mean pooling over token vectors, then L2 normalising), and why:
  the installed `sentence-transformers` broke against a newer dependency;
- [`embed_instances.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/policy_questions/embed_instances.py):
  embeds only rows whose text hash changed, so re-runs are cheap (idempotent);
- [`apps/rag-chat-app/`](https://github.com/getcommunityone/open-navigator/tree/main/apps/rag-chat-app): a streaming RAG
  chat app with pgvector retrieval in Lakebase Postgres and Databricks Model Serving for the answers.

**Try it:** `python -m llm.policy_questions.embed_instances --source decisions --state AL --limit 50`.

</details>

## 7. LLMs in a pipeline

<details>
<summary><b>Get structured, checkable output from a language model, and catch it when it's wrong</b></summary>

**The idea.** An LLM can turn a two-hour meeting transcript into decisions, votes and topics, but it can also invent
things. Production use needs fixed prompts, structured output, validation, and a check against an authoritative source.

**Read:**
- extraction: [`meeting_transcript_policy.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/meeting_transcript_policy.py)
  sends a transcript with a versioned prompt ([`prompts/policy_analysis_part_1.md`](https://github.com/getcommunityone/open-navigator/blob/main/prompts/policy_analysis_part_1.md))
  and gets structured JSON back;
- grounding: [`meeting_gap_analysis.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/meeting_gap_analysis.py)
  checks the AI summary against the official minutes and lists corrections and omissions, each quoting the source text;
- validation: [`validate_mermaid_reports.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/validate_mermaid_reports.py)
  renders the diagrams the model writes and can repair or reject them;
- LLM-as-judge: [`debate_grader.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/agents/agents/debate_grader.py)
  grades decisions on harms, solvency and topicality;
- cheap triage before expensive work: [`gatekeeper_triage.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/governance/gatekeeper_triage.py)
  asks a small multimodal Gemma model "is this a government meeting?" before running the full analysis;
- handling failures: [`genai_text_client.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/genai_text_client.py)
  tells a quota wall from an overloaded server and reacts differently.

**Why this way.** The repo's rule is "no fabricated data", so every AI output has to be checkable against the record.

**More:** [AI model evaluation](./development/ai-model-evaluation.md), [AI policy analysis](./development/ai-policy-analysis.md).

</details>

## 8. Databricks

<details>
<summary><b>Run LLM batch inference as dbt models, govern tables in Unity Catalog, serve from Lakebase</b></summary>

**The idea.** Databricks puts storage (Delta tables in Unity Catalog), compute and model serving in one place.
`ai_query` calls a model from SQL, so a dbt model can run batch LLM inference over a whole table.

**Read:**
- [`apps/agent-analysis-sync/`](https://github.com/getcommunityone/open-navigator/tree/main/apps/agent-analysis-sync):
  transcript analysis as dbt on Databricks, bronze → silver → gold. Start with
  [`bronze_transcript_analysis.sql`](https://github.com/getcommunityone/open-navigator/blob/main/apps/agent-analysis-sync/dbt/models/bronze/bronze_transcript_analysis.sql)
  (incremental, batched `ai_query` calls), then the silver models that parse the JSON;
- the bundle that deploys it: [`databricks.yml`](https://github.com/getcommunityone/open-navigator/blob/main/apps/agent-analysis-sync/databricks.yml)
  and [`resources/analysis.job.yml`](https://github.com/getcommunityone/open-navigator/blob/main/apps/agent-analysis-sync/resources/analysis.job.yml)
  (Databricks Asset Bundles: infrastructure as code);
- loading data into Unity Catalog through a Volume: [`load_transcripts_to_uc.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/databricks/load_transcripts_to_uc.py);
- serving: [`apps/lakebase-serving-sync/`](https://github.com/getcommunityone/open-navigator/tree/main/apps/lakebase-serving-sync),
  a scheduled job that pulls tables into Unity Catalog and syncs them to Lakebase Postgres.

**Try it:** the README in `apps/agent-analysis-sync/` walks through deploying with `databricks bundle deploy` and
running with `databricks bundle run`. The [Databricks Free Edition](./deployment/databricks-free-edition.md) guide
covers a free workspace.

</details>

## 9. MLOps and LLMOps

<details>
<summary><b>Know what every model call cost, how long it took, and whether it worked</b></summary>

**The idea.** A model in production needs the same care as any service: tracking, cost control, evaluation and a way
to roll back.

**Read:**
- per-call records: [`llm/usage/calls.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/calls.py)
  (tokens, attempts, wall time, success; never guessed when the API doesn't report a number);
- cost reports from sourced prices only: [`report.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/report.py),
  [`prices.yaml`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/prices.yaml);
- GPU runs recorded the same way: [`gpu.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/gpu.py),
  and the rules for paid GPUs in [GPU compute decisions](./development/gpu-compute-decisions.md);
- MLflow tracing with Unity Catalog governance: [`mlflow_classifier.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/agents/agents/mlflow_classifier.py)
  (keyword matching first, an LLM only for ambiguous cases: a hybrid of classic and LLM methods).

**Try it:** `python -m llm.usage.report --by stage`. More: [LLM and GPU usage tracking](./development/llm-usage-tracking.md).

</details>

## 10. GitHub Actions

<details>
<summary><b>Automate checks and deploys so the rules enforce themselves</b></summary>

**The idea.** A workflow is a YAML file that runs jobs on events (a push, a pull request, a button press). Required
checks block a merge until they pass.

**Read:**
- [`ci-build-test.yml`](https://github.com/getcommunityone/open-navigator/blob/main/.github/workflows/ci-build-test.yml):
  frontend build, docs build, backend tests, API types, and a Docker build that runs only when Docker files change;
- [`pr-conventions.yml`](https://github.com/getcommunityone/open-navigator/blob/main/.github/workflows/pr-conventions.yml)
  with [`pr_conventions.py`](https://github.com/getcommunityone/open-navigator/blob/main/.github/scripts/pr_conventions.py):
  a custom check that fails a PR whose linked issue lacks its four parts;
- [`deploy-databricks.yml`](https://github.com/getcommunityone/open-navigator/blob/main/.github/workflows/deploy-databricks.yml):
  deploys the Databricks bundle on merge, and skips cleanly when the secrets aren't set;
- [`gpu-diarize-modal.yml`](https://github.com/getcommunityone/open-navigator/blob/main/.github/workflows/gpu-diarize-modal.yml):
  an on-demand GPU job (speech-to-text and speaker separation) with a cap per run and a cost row per item.

**Try it:** open any pull request's **Checks** tab to see these run.

</details>

## 11. Ontologies and taxonomies

<details>
<summary><b>Give things agreed names and a hierarchy, so data from different sources lines up</b></summary>

**The idea.**
- A **taxonomy** is a hierarchy of categories.
- An **ontology** adds relationships between them.
- A **controlled vocabulary** is the agreed list of terms.

Using published standards means other people's data uses the same labels as yours.

**Read:**
- a hierarchy in SQL: [`int_tags__closure.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/intermediate/int_tags__closure.sql)
  builds a **closure table** (every ancestor–descendant pair), so "everything under category E" is one filter instead
  of a recursive query. [`int_ntee__breadcrumb.sql`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/intermediate/int_ntee__breadcrumb.sql)
  walks the NTEE nonprofit classification;
- published vocabularies kept as seeds:
  - [`cap_topic.csv`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/seeds/cap_topic.csv): Comparative Agendas Project policy topics;
  - [`policy_frame.csv`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/seeds/policy_frame.csv): Policy Frames Codebook, how an issue is argued;
  - [`policy_theme_cofog.csv`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/seeds/policy_theme_cofog.csv): the UN's COFOG classification of government spending;
- a registry of recurring questions: [`curated_policy_questions.csv`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/seeds/curated_policy_questions.csv).

**Try it:** `cd dbt_project && dbt seed --select cap_topic policy_frame` loads two vocabularies into the warehouse.

</details>

## 12. Data contracts

<details>
<summary><b>Promise the shape of a table to the people who use it, and check the promise automatically</b></summary>

**The idea.** A data contract states a table's columns, types, keys and meaning. If a change would break it, CI fails
before users notice. This repo uses the Open Data Contract Standard (ODCS).

**Read:**
- one contract per served table: [`dbt_project/contracts/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/contracts),
  for example [`bills.odcs.yaml`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/contracts/bills.odcs.yaml);
- the generator and checker: [`models/odcs.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/datamodels/models/odcs.py)
  builds contracts from dbt's `schema.yml` and validates them against the published schema;
- enforcement inside dbt: model contracts with typed columns, primary and foreign keys, for example
  [`_schema_jurisdiction_property_tax_rate.yml`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/_schema_jurisdiction_property_tax_rate.yml).

**Try it:** `cd packages/datamodels && python -m models.odcs --write` regenerates the contracts; `git diff` shows what
changed. More: [data contracts](./development/data-contracts.md).

</details>

## 13. Data products

<details>
<summary><b>Treat a set of tables as a product with an owner, a purpose and its contracts</b></summary>

**The idea.** A data product packages related tables with their contracts, ownership and access, so a consumer gets one
documented thing instead of a pile of tables. This repo uses the Open Data Product Standard (ODPS).

**Read:**
- the product: [`open-navigator-public-api.odps.yaml`](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/contracts/products/open-navigator-public-api.odps.yaml)
  gathers the public API's table contracts into one product;
- the code: [`models/odps.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/datamodels/models/odps.py);
- the decision record: [data contracts, "The data product"](./development/data-contracts.md#the-data-product-odps).

**Try it:** read the product file top to bottom, then open one of the contracts it lists.

</details>

## Contributing as a student

Good first issues are small and well described: every issue here has a Problem, Done when, Contract and Read first
section ([how we work](https://github.com/getcommunityone/open-navigator/blob/main/AGENTS.md)). Browse the
[open issues](https://github.com/getcommunityone/open-navigator/issues), pick one, and say in a comment that you're
taking it.
