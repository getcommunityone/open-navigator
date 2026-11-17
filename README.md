---
title: Open Navigator
emoji: 🏛️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Open Navigator
**See what your local government decided, with the record to prove it.**

**The goal: one map for every community.** The U.S. has 91,438 local governments (U.S. Census Bureau, 2025), and
each publishes its agendas, minutes, videos and budgets its own way. Open Navigator, the open-source engine behind
[CommunityOne](https://www.communityone.com) (a 501(c)(3) nonprofit), reads those public records, plus nonprofit
filings and Census data, and shows what was decided, where, and the passage from the record that says so. Nothing on
the site is a made-up number: when data is missing, it says so.

**Coverage today:** 1,926,908 nonprofits, 153,235 meetings and events, 34,289 government officials and 4,495 decisions extracted by AI, from [/api/stats](https://www.communityone.com/api/stats) (snapshot dated June 5, 2026, read November 14, 2026). Jurisdiction counts are left out until that endpoint reports them correctly ([#291](https://github.com/getcommunityone/open-navigator/issues/291)).

**Live:** [communityone.com](https://www.communityone.com) · [docs](https://www.communityone.com/docs) ·
[API](https://www.communityone.com/api) · Apache 2.0

<a href="web_docs/docs/pitch/full-text-and-notes.md"><img src="web_docs/static/img/deck-cover.png" alt="Local decisions shape daily life. Most people never see them." width="480"></a>

| For | Go to |
|---|---|
| **Executives and funders** (12 slides, 10 minutes) | [read the pitch with speaker notes](web_docs/docs/pitch/full-text-and-notes.md) · [slides](https://www.communityone.com/docs/deck/) ([source](web_docs/static/deck/index.html): download and open in a browser) |
| **Residents** | [the app](https://www.communityone.com) · [guide for citizens](web_docs/docs/for-citizens.md) |
| **Advocates and nonprofit leaders** | [guide for advocates](web_docs/docs/for-advocates.md) · [accountability strategy](web_docs/docs/guides/accountability-strategy.md) |
| **Researchers and data analysts** | [data sources](web_docs/docs/data-sources/overview.md) · [data model](web_docs/docs/data-sources/data-model-erd.md) · [citations](CITATIONS.md) |
| **Developers and data engineers** | [code walkthrough](web_docs/docs/development/code-walkthrough.md) · [quick start](web_docs/docs/quickstart.md) · [architecture](web_docs/docs/architecture.md) · [how we work](AGENTS.md) |
| **Data platform and DataOps engineers** | [DataOps walkthrough](web_docs/docs/development/dataops-walkthrough.md): retries, recovery, data quality, AI observability, two real incidents, and what isn't built yet |
| **Students** | [learning path](web_docs/docs/for-students.md): statistics, SQL and window functions, data modeling, dbt, master data management, logistic regression, clustering, embeddings, LLMs, Databricks, MLOps, GitHub Actions, AWS, Azure, security and secrets, ontologies, data contracts and data products, each with a code walkthrough |

**This quarter: data center accountability** (planned, not built yet). Residents ask what's being built near them,
who approved it, what it does to their bill and whether the jobs are real. The plan, October to December 2026:
[epic #236](https://github.com/getcommunityone/open-navigator/issues/236).

<details>
<summary><b>The six stories</b></summary>

- Job promises, on the record: [jobs split by phase](https://github.com/getcommunityone/open-navigator/issues/246) ·
  [promise attributed to a speaker](https://github.com/getcommunityone/open-navigator/issues/247) ·
  [live application links](https://github.com/getcommunityone/open-navigator/issues/248)
- The pipeline near me: [proposed sites near me](https://github.com/getcommunityone/open-navigator/issues/249) ·
  [site matched to a coming agenda](https://github.com/getcommunityone/open-navigator/issues/250) ·
  [alerts ranked by local concern](https://github.com/getcommunityone/open-navigator/issues/251)

They build on the meeting citations in the [CORE epic](https://github.com/getcommunityone/open-navigator/issues/235).
</details>

Each role has more below. Click to open.

<details>
<summary><b>Executives and funders</b>: the pitch in ten minutes</summary>

The [slideshow](https://www.communityone.com/docs/deck/) covers who it is for, the problem, what it does, the story
lenses, the policy model, how the pipeline works, the trust rules, what is open, this quarter's data center work,
an honest status, and the ask.
Press **N** for speaker notes, **S** for the speaker view. The [full text and notes](web_docs/docs/pitch/full-text-and-notes.md)
has every slide's words, for reading on a phone or searching.

Where it stands: live and useful, and still uneven. Meeting analysis is deep in a few states and thin elsewhere, and
it is a small nonprofit project with one maintainer. Data, review and pilot communities help most. Contact:
johnbowyer@communityone.com.

To edit the deck, change a slide in `web_docs/deck/slides/` and run `node web_docs/scripts/build-deck.mjs`.
</details>

<details>
<summary><b>Residents</b>: what did my city or school board decide?</summary>

- Search a topic at [communityone.com](https://www.communityone.com), pick your state or city, and open any result to
  see the passage from the record it came from.
- Set up **Close to Home** for a feed of the places and issues you choose.
- Story lenses point to what is worth a look: **Contested** (split votes), **Money Moves** (contracts, grants, budget
  changes), **Raised Eyebrows** (unusual patterns, for a person to review), **Moving Fast** and **Watch Next** (votes
  coming up, where you can still speak).
- More: [guide for citizens](web_docs/docs/for-citizens.md), [community resources](web_docs/docs/citizens/community-resources.md),
  [voter registration](web_docs/docs/citizens/voter-registration.md).
</details>

<details>
<summary><b>Advocates and nonprofit leaders</b>: where is my issue moving?</summary>

- **Policy questions** follow one issue across places: each vote links to the question behind it and the arguments
  made for and against it.
- **Money and talk** puts budgets and spending next to what officials said in meetings.
- **Nonprofits**: IRS filings (Form 990) by place and cause.
- More: [guide for advocates](web_docs/docs/for-advocates.md), [accountability strategy](web_docs/docs/guides/accountability-strategy.md),
  [legislative tracking](web_docs/docs/guides/legislative-tracking.md), [case study: Tuscaloosa](web_docs/docs/case-studies/tuscaloosa-complete.md).
</details>

<details>
<summary><b>Researchers and data analysts</b>: what does the record say, at scale?</summary>

- **Open datasets** on Hugging Face: [publishing guide](web_docs/docs/guides/huggingface-publishing.md).
- **Data model**: [entity diagram](web_docs/docs/data-sources/data-model-erd.md), [marts](web_docs/docs/data-sources/marts-erd.md),
  [data contracts](web_docs/docs/development/data-contracts.md).
- **Sources and licences**: [data sources overview](web_docs/docs/data-sources/overview.md), [CITATIONS.md](CITATIONS.md).
  Meeting data follows the Council Data Project's model; places use Open Civic Data IDs.
- **AI assistants**: an MCP server lets Claude and other assistants query the data. [MCP guide](web_docs/docs/integrations/mcp-server.md).
</details>

<details>
<summary><b>Students</b>: learn AI and data engineering from a real system</summary>

**Start with the [learning path](web_docs/docs/for-students.md):** each topic gives the idea in plain words, the code to
read, why it's built that way, and something to try. Topics don't depend on each other.

| Topic | Learn it from |
|---|---|
| Basic statistics | Median vs mean, p90, outliers and minimum sample sizes in [minutes publish lag](dbt_project/models/marts/jurisdiction_minutes_publish_lag.sql) |
| SQL and window functions | `row_number`, `lag`, `ntile`, recursive CTEs in [int_civic__item_signals.sql](dbt_project/models/intermediate/int_civic__item_signals.sql) |
| Data modeling | Grain, keys and a many-to-many bridge in [mdm_bridge_person_jurisdiction.sql](dbt_project/models/marts/mdm_bridge_person_jurisdiction.sql) |
| dbt and medallion layers | [dbt_project/models/](dbt_project/models): bronze → staging → intermediate → marts, with tests and seeds |
| Master data management | Golden records and entity resolution with Splink in [mdm/linker.py](packages/ingestion/src/ingestion/mdm/linker.py) |
| Logistic regression | Log-odds and the logistic function, as Splink uses them in [mdm/settings.py](packages/ingestion/src/ingestion/mdm/settings.py); a trained example is a good first issue ([#373](https://github.com/getcommunityone/open-navigator/issues/373)) |
| Clustering | HDBSCAN with a noise bucket in [cluster.py](packages/llm/src/llm/policy_questions/cluster.py) |
| Embeddings and RAG | [encoder.py](packages/llm/src/llm/policy_questions/encoder.py) and the [RAG chat app](apps/rag-chat-app) |
| LLMs | Extraction, grounding against minutes, LLM-as-judge: [meeting_gap_analysis.py](packages/llm/src/llm/gemini/meeting_gap_analysis.py) |
| Databricks | Asset bundles (DABs) with dev/free/prod targets, `ai_query` batch inference in dbt: [agent-analysis-sync](apps/agent-analysis-sync) |
| MLOps and LLMOps | Per-call usage and cost records: [llm/usage](packages/llm/src/llm/usage) |
| GitHub Actions | [.github/workflows](.github/workflows): CI, a custom PR check, deploys, on-demand GPU |
| AWS | Sharded Lambda scans and public S3 reads without credentials: [lambda_handler.py](packages/accessibility/src/accessibility/lambda_handler.py) |
| Azure | Terraform for subscriptions, budgets and a Databricks workspace: [infra/azure](infra/azure) |
| Security and secrets | OIDC sign-in with no stored secret, service principals, where secrets live, and an app-security fix ([#361](https://github.com/getcommunityone/open-navigator/pull/361)) |
| Ontologies | NTEE closure table, CAP topics, Policy Frames, COFOG: [int_tags__closure.sql](dbt_project/models/intermediate/int_tags__closure.sql), [seeds](dbt_project/seeds) |
| Data contracts and products | ODCS contracts and an ODPS product: [dbt_project/contracts](dbt_project/contracts) |

</details>

<details>
<summary><b>Data platform and DataOps engineers</b>: how the pipelines fail, recover and get checked</summary>

**Start with the [DataOps walkthrough](web_docs/docs/development/dataops-walkthrough.md):** each capability with what
it does, the code, why it's built that way and how to see it run.

| Capability | In short | Code |
|---|---|---|
| Failure detection and retry | Errors classified by cause: retry transient ones with backoff and jitter, stop at a quota wall, rotate off an overloaded model | [HTTP client](packages/core-lib/src/core_lib/http/client.py) · [Gemini client](packages/llm/src/llm/gemini/genai_text_client.py) |
| Stuck-run recovery | Batch runs with no activity are cancelled and their units marked failed for a rerun | [batch_job_status.py](api/batch_jobs/batch_job_status.py) |
| Safe, repeatable reruns | A second run changes nothing; a file is deleted only if it's byte-identical | [transcript_cache_paths.py](packages/llm/src/llm/gemini/transcript_cache_paths.py) |
| Data quality and contracts | dbt tests, coverage-bias models, enforced model contracts, ODCS contracts in CI, `null` instead of a made-up number | [dbt tests](dbt_project/tests) · [odcs.py](packages/datamodels/models/odcs.py) |
| AI in production | Every model call recorded (tokens, attempts, latency); output validated; summaries checked against official minutes; human exclusions | [usage](packages/llm/src/llm/usage) · [gap analysis](packages/llm/src/llm/gemini/meeting_gap_analysis.py) |
| Observability | OpenTelemetry spans from the browser through the API | [telemetry.py](api/telemetry.py) · [api.ts](web_app/src/lib/api.ts) |
| Standards | Issue-first rule enforced in CI, one review rubric for every PR, decisions written down | [AGENTS.md](AGENTS.md) · [pr_conventions.py](.github/scripts/pr_conventions.py) |

**Two real incidents (November 2026):** a cache cleanup that never converged
([#347](https://github.com/getcommunityone/open-navigator/pull/347),
[#215](https://github.com/getcommunityone/open-navigator/pull/215)), and sign-in down on Neon's pooled endpoint
([#368](https://github.com/getcommunityone/open-navigator/pull/368)).

**Not built yet:** paging an on-call person, telling a table's users when its refresh fails, learned anomaly detection,
AI root-cause assessment, and health checks for each database connection.

</details>

<details>
<summary><b>Developers and data engineers</b>: run it, change it</summary>

**Start with the [code walkthrough](web_docs/docs/development/code-walkthrough.md):** twelve steps in run order, from
finding governments' websites to the page in the app, each with its code, command and output, plus a table of where to
change things.

**Stack.** FastAPI (`api/`), React + Vite + TypeScript (`web_app/`), Docusaurus (`web_docs/`), dbt on PostgreSQL
(`dbt_project/`: bronze → staging → intermediate → marts), shared Python libraries in `packages/` (a uv workspace).
`scripts/` is legacy and frozen: new Python goes in `packages/`. Rules: [CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md).

**Run it locally** (API on 8001, app on 5173, docs on 3000):

```bash
git clone https://github.com/getcommunityone/open-navigator.git && cd open-navigator
./install.sh                        # Python backend (.venv + .env); on Windows: .\install.ps1
cd web_app && npm install && cd ..
cd web_docs && npm install && cd ..
./start-all.sh                      # on Windows: .\start-all.ps1
```

Don't use `uv sync` for the backend: the root `pyproject.toml` is a workspace and skips `requirements.txt`. Full setup,
including restoring a warehouse snapshot: [quick start](web_docs/docs/quickstart.md).

**Data pipeline.** Python only for ingestion, AI extraction and orchestration; every SQL transformation is dbt.

```bash
cd dbt_project && dbt run && dbt test
```

More: [dbt strategy](web_docs/docs/development/dbt-etl-strategy.md), [entity resolution](web_docs/docs/development/bronze-to-production-merge.md),
[dbt project](dbt_project/README.md), [refactor roadmap](web_docs/docs/development/cleanup-roadmap.md).

**Deploy.** [Hugging Face Spaces](web_docs/docs/deployment/huggingface-spaces.md) (this README's front matter configures
the Space), [Databricks Apps](web_docs/docs/deployment/databricks-apps.md), or `docker-compose up -d`.

**AI and agents.** Gemini reads meeting transcripts and extracts decisions, quotes and amounts; Jev screens
transcripts first. Coding agents (Claude Code and others) follow [AGENTS.md](AGENTS.md). Long agent sessions get
*compacted*: when a conversation outgrows the model's context window, older turns are replaced by a summary and exact
details can be lost. So anything that matters goes into an issue, a PR or a docs page, never only the chat, and a
summary is never used as evidence. More: [how Open Navigator uses AI](web_docs/docs/development/ai-overview.md)
(including [compaction](web_docs/docs/development/ai-overview.md#compaction)) and
[context engineering](web_docs/docs/development/context-engineering.md).

**Test.** `pytest` for the backend; CI also builds the app and the docs and checks the slideshow is up to date.

**Contribute.** Every change starts from a GitHub issue with four parts (Problem, Done when, Contract, Read first),
on a branch `<type>/<issue>-<slug>`, through a pull request that closes it. See [AGENTS.md](AGENTS.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).
</details>

---

Sources: U.S. Census Bureau, [Government Organization Summary Report: 2022 & 2025](https://www.census.gov/library/publications/2026/econ/govtorg2225.html).
Datasets and research used here: [CITATIONS.md](CITATIONS.md) (including MeetingBank, Hu et al., ACL 2023).
All generated content should be reviewed by a person before use in advocacy.
Issues: [github.com/getcommunityone/open-navigator/issues](https://github.com/getcommunityone/open-navigator/issues) ·
johnbowyer@communityone.com · Apache 2.0, see [LICENSE](LICENSE).
