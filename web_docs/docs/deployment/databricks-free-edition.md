---
title: Databricks Free Edition
description: Run the transcript analysis and land crawl output in a free Databricks workspace, deployed by CI the way the Health Transformation Lab does it.
---

# Databricks Free Edition

**What it's for:** processing that shouldn't depend on the maintainer's laptop. The `free` target of the
`agent-analysis-sync` bundle runs the transcript analysis (dbt with `ai_query`) on serverless compute, and creates the
landing volume the nightly crawl and the Colab GPU steps write to
([#293](https://github.com/getcommunityone/open-navigator/issues/293)). It is set up the same way as the Health
Transformation Lab's dev workspace: a service principal, a GitHub environment, and a deploy on every merge.

<details>
<summary><b>Limits to plan around</b></summary>

- Serverless only; small compute with a daily usage limit. Over it, compute stops for the rest of the day (data stays).
- One SQL warehouse (2X-Small), at most 5 concurrent job tasks per account, one active pipeline per type.
- Outbound internet is limited to trusted domains unless you verify with LinkedIn. That's why crawling runs on GitHub
  Actions, not here.
- Not for commercial use. Check the terms fit CommunityOne's use.
- One workspace per account. If the Health Transformation Lab already uses your Free Edition workspace, this bundle can
  share it (its own catalog, `open_navigator`), and the two projects share the daily limit.
- Not yet checked on Free Edition: whether the `databricks-gpt-oss-120b` pay-per-token endpoint is available to
  `ai_query` there. The first run says; if not, set `primary_model` to an endpoint that is.

Source: [Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations).
</details>

<details>
<summary><b>One-time setup (about 15 minutes)</b></summary>

1. Sign up at [databricks.com/learn/free-edition](https://www.databricks.com/learn/free-edition) (or use the workspace
   you already have), and choose **Verify with LinkedIn** in the workspace.
2. Log in from a terminal: `databricks auth login --host https://<workspace>`.
3. Run `apps/agent-analysis-sync/setup/create_service_principal.sh free`. It creates the service principal and admin
   group, the `open_navigator` catalog, and the grants, then prints the next commands.
4. Make the principal's OAuth secret (90 days) and put it straight into the GitHub environment `free`, with the
   variables `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID`, exactly as the script prints. Never paste the secret into
   a file or chat.
5. Run **Actions → Deploy to Databricks Free Edition → Run workflow**. It validates and deploys; tick
   *run_analysis* to also run one batch.
6. Load transcripts once from a machine with the local warehouse, pointing the loader at the Free Edition workspace
   (its defaults are the old Azure workspace):
   `python -m ingestion.databricks.load_transcripts_to_uc --profile <free profile> --warehouse-id <starter warehouse id> --catalog open_navigator --limit 25`.
</details>

<details>
<summary><b>What the deploy creates</b></summary>

| Object | Name |
|---|---|
| Analysis schema | `open_navigator.open_navigator_analysis` |
| Landing schema and volume | `open_navigator.open_navigator_landing.crawl` |
| Job (schedule paused) | `[free] agent-analysis-sync` |

Batches are 25 transcripts (`analysis_batch_size`), small enough to stay under the daily limit. Raise it once a run
shows how much quota a batch uses.
</details>

<details>
<summary><b>Credential</b></summary>

| Credential | Where it's made | Scope | Goes to | Lifetime |
|---|---|---|---|---|
| `open_navigator_free_sp` OAuth secret | Databricks CLI: `service-principal-secrets-proxy create` (printed by the setup script) | the service principal: workspace access, SQL access, ALL PRIVILEGES on `open_navigator` | GitHub environment `free`, secret `DATABRICKS_CLIENT_SECRET` | 90 days; renew 14 days before |
</details>
