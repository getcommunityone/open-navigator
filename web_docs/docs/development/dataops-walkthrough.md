---
title: DataOps walkthrough
sidebar_label: DataOps walkthrough
description: How Open Navigator's pipelines detect failures, recover, check data quality and keep AI output honest, with a link to the code for each piece and what isn't built yet.
format: md
---

# DataOps walkthrough

**How the pipelines run, fail, recover and get checked, and where the AI fits in.** This page covers the systems
*around* the pipelines (retries, recovery, data quality, AI observability, standards), not the pipelines themselves;
for those, see the [code walkthrough](./code-walkthrough.md). Each section says what the piece does, links the code,
says why it's built that way, and shows how to see it run. The [last section](#not-built-yet) lists what isn't
built.

| Capability | What exists | Code |
|---|---|---|
| [Failure detection and retry](#1-failure-detection-and-retry) | Failures classified by cause; backoff with jitter; rotate off an overloaded model | [`core_lib/http/client.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/core-lib/src/core_lib/http/client.py) · [`genai_text_client.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/genai_text_client.py) |
| [Stuck-run recovery](#2-stuck-run-recovery) | Batch runs with no activity are cancelled and their units marked failed | [`batch_job_status.py`](https://github.com/getcommunityone/open-navigator/blob/main/api/batch_jobs/batch_job_status.py) |
| [Safe, repeatable reruns](#3-safe-repeatable-reruns) | Cleanup converges and never deletes a file that differs | [`transcript_cache_paths.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/transcript_cache_paths.py) |
| [Data quality and contracts](#4-data-quality-and-contracts) | dbt tests, coverage-bias models, enforced model contracts, ODCS contracts checked in CI | [`dbt_project/tests/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/tests) · [`models/odcs.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/datamodels/models/odcs.py) |
| [AI in production](#5-ai-in-production) | Per-call usage records, output validation and repair, grounding against official minutes, human exclusions | [`llm/usage/`](https://github.com/getcommunityone/open-navigator/tree/main/packages/llm/src/llm/usage) · [`validate_mermaid_reports.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/validate_mermaid_reports.py) · [`meeting_gap_analysis.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/meeting_gap_analysis.py) |
| [Observability](#6-observability) | OpenTelemetry spans in the API and the browser; structured logs | [`api/telemetry.py`](https://github.com/getcommunityone/open-navigator/blob/main/api/telemetry.py) · [`web_app/src/lib/api.ts`](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/lib/api.ts) |
| [Standards that scale](#7-standards-that-scale) | Issue-first rule enforced in CI, a shared review rubric, written decisions | [`AGENTS.md`](https://github.com/getcommunityone/open-navigator/blob/main/AGENTS.md) · [`pr_conventions.py`](https://github.com/getcommunityone/open-navigator/blob/main/.github/scripts/pr_conventions.py) · [`review-rubric.md`](https://github.com/getcommunityone/open-navigator/blob/main/.claude/review-rubric.md) |
| [Two real incidents](#8-two-real-incidents) | November 2026: a cleanup that never converged, and a sign-in outage | [#347](https://github.com/getcommunityone/open-navigator/pull/347) · [#215](https://github.com/getcommunityone/open-navigator/pull/215) · [#368](https://github.com/getcommunityone/open-navigator/pull/368) |

## 1. Failure detection and retry

<details>
<summary><b>Retry what's transient, stop on what isn't, and know which is which</b></summary>

- **Shared HTTP client** ([`core_lib/http/client.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/core-lib/src/core_lib/http/client.py)): every
  scraper can use one client that retries only the statuses worth retrying (408, 425, 429, 500, 502, 503, 504), up to
  `max_attempts` (5 by default), with exponential backoff plus random jitter so parallel workers don't retry in
  lockstep. A run of failures that outlasts the budget raises a clear error instead of crashing the caller.
- **AI calls classify the failure** ([`genai_text_client.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/genai_text_client.py)).
  A Gemini error is sorted into one of four outcomes, each handled differently:
  - transient network drop → retry quickly (`GenAITransientGiveUp` when the budget runs out);
  - daily quota wall (429 / `RESOURCE_EXHAUSTED`) → stop; retrying burns time for nothing (`GenAIDailyQuotaGiveUp`);
  - server overload (502/503/504, `UNAVAILABLE`) → rotate *temporarily* off the congested model with a short cooldown
    (`GenAIServerOverloadGiveUp`);
  - model not available → drop that model rather than crash the batch (`GenAIModelUnavailableGiveUp`).

  The code reads the server's suggested retry delay (`retry in Ns` / `retryDelay`) when it gives one.
- **Upstream politeness** ([`api/routes/geocode.py`](https://github.com/getcommunityone/open-navigator/blob/main/api/routes/geocode.py)): identical address lookups made
  at the same time share one upstream call, a failed call still counts against the rate budget (so an outage can't
  turn into a retry storm), and a 429 passes a numeric `Retry-After` back to the browser.

**Why:** treating every error the same either hammers a provider that has said "stop for today" or gives up on a blip.
Classifying first lets each failure get the response it needs.

**See it:** `packages/core-lib` and `packages/llm` tests; `tests/test_geocode_proxy.py` (coalescing, timeouts, 429,
malformed responses).

</details>

## 2. Stuck-run recovery

<details>
<summary><b>A batch that stops reporting progress gets cancelled, not left "running" forever</b></summary>

[`api/batch_jobs/batch_job_status.py`](https://github.com/getcommunityone/open-navigator/blob/main/api/batch_jobs/batch_job_status.py), `_maybe_stale_cancel_batch`:

- A batch run (for example, AI analysis across one state's jurisdictions) records activity as it goes.
- If a `running` batch shows no activity for `BATCH_JOB_INACTIVITY_SECONDS` (default 3,600, minimum 60), it is marked
  `cancelled` with the reason stored in its config (`stale_cancel_reason`), and each jurisdiction still `running` is
  marked `failed` with exit code `-1` so it can be picked up again.
- Detached pipeline launches (Discover / catalog / captions / …) also warn on the Batch Job Status page when the
  launch log goes quiet for `BATCH_JOB_LAUNCH_WARN_SECONDS` (default 900) or when the log shows Surfshark/VPN down
  ([#750](https://github.com/getcommunityone/open-navigator/issues/750)). Discover aborts the whole run on
  `VpnRequiredError` instead of skipping county by county.
- The admin dashboard ([`batch_job_dashboard.py`](https://github.com/getcommunityone/open-navigator/blob/main/api/batch_jobs/batch_job_dashboard.py)) shows per-state
  progress; launching, stopping and reading logs require an admin since
  [#361](https://github.com/getcommunityone/open-navigator/pull/361).

**Why:** a crashed worker can't report that it crashed. Inactivity is the signal that's always available.

</details>

## 3. Safe, repeatable reruns

<details>
<summary><b>Run it twice and the second run changes nothing; never delete data that differs</b></summary>

The transcript cache cleanup ([`transcript_cache_paths.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/transcript_cache_paths.py),
`fix_policy_cache_dates_from_title` and `_safe_policy_move`) renames AI outputs to `YYYY-MM-DD_<title>.*`:

- **Converges:** multi-part suffixes (`.diagrams.md`, `.meta.json`, `.mermaid-errors.json`) are split off before
  parsing, and names already corrupted by earlier runs are healed once, then left alone.
- **Never loses data:** when two files map to the same name, the source is deleted *only* if the bytes are identical
  (SHA-256). Otherwise both are kept, counted as `skipped_collision` and logged for a person to resolve.
- **Dry run tells the truth:** destinations claimed earlier in the same pass are tracked, so `--dry-run` predicts the
  collisions the real run would hit.
- **Every action logged:** moves, deletions and collisions go to `loguru`.

**See it:** [`packages/llm/tests/test_policy_cache_cleanup_idempotent.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/tests/test_policy_cache_cleanup_idempotent.py)
(second run moves nothing) and [`test_policy_cache_cleanup_collisions.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/tests/test_policy_cache_cleanup_collisions.py)
(different files survive, identical copies are removed, dry run matches the real run). The story is in
[incident 1](#8-two-real-incidents).

</details>

## 4. Data quality and contracts

<details>
<summary><b>Checks in dbt, contracts in CI, and an honest empty state instead of a made-up number</b></summary>

- **Rule-based tests in dbt** ([`dbt_project/tests/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/tests)), run by `dbt build`. Examples:
  - `assert_mdm_person_not_overmerged.sql`: entity resolution hasn't merged too many records into one person;
  - `assert_recorded_video_meeting_date_not_future.sql`: no recorded meeting dated in the future;
  - `assert_interestingness_weights_sane.sql`: the story-lens scoring weights stay in range.
- **Coverage-bias monitoring:** the `dq_jurisdiction_mapping_summary*` models in [`dbt_project/models/`](https://github.com/getcommunityone/open-navigator/tree/main/dbt_project/models)
  measure how well jurisdictions are matched, broken down by ACS income level and population tier, so gaps that fall
  on poorer or smaller places show up.
- **Enforced model contracts:** served marts declare column types, primary keys and foreign keys, and dbt refuses to
  build a table that doesn't match (for example `jurisdiction_property_tax_rate`).
- **Data contracts for the public API:** every served table gets an ODCS contract generated from dbt and checked in
  CI ([`packages/datamodels/models/odcs.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/datamodels/models/odcs.py), decision record:
  [data contracts](./data-contracts.md)).
- **No fabricated data:** a hard rule in [`CLAUDE.md`](https://github.com/getcommunityone/open-navigator/blob/main/CLAUDE.md). When a value is missing, the API returns
  `null` and the UI says so. For example, the money modal's income slider starts empty unless the real ACS median is
  loaded ([#354](https://github.com/getcommunityone/open-navigator/pull/354)).

**Caught this way:** the national stats served `0` jurisdictions and more nonprofit leaders than people
([#291](https://github.com/getcommunityone/open-navigator/issues/291)). The leaders figure turned out to count
positions (a person at an org), not people, and is now labelled that way.

</details>

## 5. AI in production

<details>
<summary><b>Measure every call, validate the output, ground it in the official record, keep a person in the loop</b></summary>

- **Every model call is recorded** ([`llm/usage/calls.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/calls.py)): input,
  cached and output tokens, thinking tokens, wall time including retries, number of attempts, success, and labels such
  as stage and jurisdiction. A count the API didn't report stays `None`; it is never guessed. GPU steps are recorded
  the same way ([`gpu.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/gpu.py)).
- **Cost only from sourced prices:** `python -m llm.usage.report --by stage` totals by day, model and stage, and shows
  a cost only where [`prices.yaml`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/usage/prices.yaml) has a dated, sourced price. See
  [LLM and GPU usage tracking](./llm-usage-tracking.md).
- **Validate and repair generated output:** AI reports include Mermaid diagrams.
  [`validate_mermaid_reports.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/validate_mermaid_reports.py) renders them,
  `--repair` runs a sanitizer, and `--strict` exits non-zero so CI can block a broken report.
- **Ground against the official record:** [`meeting_gap_analysis.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/meeting_gap_analysis.py)
  compares the AI summary of a meeting video with the official minutes. It lists corrections where the minutes
  contradict the AI, enrichments (addresses, ordinance numbers, dollar amounts) and omissions (things the minutes
  leave out). Every item must quote the supplied texts. If no document text was extracted, it doesn't call the model.
- **Human exclusions:** a person can pull a non-meeting upload out of the pipeline
  ([`policy_exclusions.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/llm/src/llm/gemini/policy_exclusions.py)). Its files move to
  `05_exceptions/` with a reason in a manifest, and later runs skip it.
- **Evaluation approach:** [AI model evaluation](./ai-model-evaluation.md) describes comparative and
  LLM-as-judge methods for extractions that have no single right answer.

</details>

## 6. Observability

<details>
<summary><b>Traces from the browser to the database, and logs that say what happened</b></summary>

- **API:** [`api/telemetry.py`](https://github.com/getcommunityone/open-navigator/blob/main/api/telemetry.py) instruments FastAPI with OpenTelemetry. Spans wrap discrete
  operations (database queries, external calls). Traces export over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- **Browser:** `tracedFetch` in [`web_app/src/lib/api.ts`](https://github.com/getcommunityone/open-navigator/blob/main/web_app/src/lib/api.ts) starts a span per API call
  and records the status, so a slow page can be followed into the API.
- **Logs:** packages log with `loguru`, including retries, give-ups, moves, deletions and collisions. Security events
  (a dropped unsafe redirect, a refused admin request) are logged in the auth code.

</details>

## 7. Standards that scale

<details>
<summary><b>How changes get made, reviewed and recorded, for people and AI agents alike</b></summary>

- **Issues first:** every change starts from an issue with four parts (Problem, Done when, Contract, Read first)
  ([`AGENTS.md`](https://github.com/getcommunityone/open-navigator/blob/main/AGENTS.md)). CI enforces it on every pull request
  ([`.github/scripts/pr_conventions.py`](https://github.com/getcommunityone/open-navigator/blob/main/.github/scripts/pr_conventions.py)).
- **One review rubric:** every PR gets a written review against [`.claude/review-rubric.md`](https://github.com/getcommunityone/open-navigator/blob/main/.claude/review-rubric.md),
  saved as `pull_requests/pr-<n>-review.md`. It covers secrets, fabricated data, personal data and destructive
  data changes, and each finding is verified against the code before it's kept.
- **Specialists:** scoped work goes to data/dbt, API, frontend or Python-package specialist agents
  ([`.claude/agents/`](https://github.com/getcommunityone/open-navigator/tree/main/.claude/agents)), each with the repo's rules built in.
- **Decisions written down:** choices and their reasons live under `web_docs/docs/development/`, for example
  [GPU compute decisions](./gpu-compute-decisions.md) (a paid GPU run needs the owner's explicit yes, and usage is read
  before and after).
- **Contributors' work carried forward:** when a contributor's branch fell behind, a maintainer merged `main`,
  fixed what broke and kept their authorship, for example
  [#361](https://github.com/getcommunityone/open-navigator/pull/361) (from #208) and
  [#363](https://github.com/getcommunityone/open-navigator/pull/363) (from #210).

</details>

## 8. Two real incidents

<details>
<summary><b>Incident 1: a cleanup that never converged (November 2026)</b></summary>

- **Signal:** the transcript cache cleanup moved about 1,000 files on every full run and never settled
  ([#48](https://github.com/getcommunityone/open-navigator/issues/48)).
- **Root cause:** `Path.stem` drops only the last suffix, so `x.diagrams.md` parsed to the title `x.diagrams` and each
  run renamed it to `x.diagrams.diagrams.md`. Reproduced on a synthetic folder: 4 moves on every run, forever.
- **First fix and what review caught:** [#347](https://github.com/getcommunityone/open-navigator/pull/347) stripped
  compound suffixes. Its review reproduced a data-loss path: a caption sidecar could overwrite its transcript. That was
  fixed before merge, with a test that checks the whole file set and contents across runs.
- **Hardened:** [#215](https://github.com/getcommunityone/open-navigator/pull/215) (a contributor's fuller fix) was
  finished so the cleanup deletes only byte-identical copies, logs every action, and makes the dry run predict
  collisions. A related gap is open as [#359](https://github.com/getcommunityone/open-navigator/issues/359).

</details>

<details>
<summary><b>Incident 2: sign-in down on Neon's pooled endpoint (November 15, 2026)</b></summary>

- **Signal:** sign-in returned a 503 ("could not start the login session") while the rest of the site worked.
- **Diagnosis:** `/api/stats` still answered, which ruled out the database being down and pointed at the login
  path's own connection. The container log showed `unsupported startup parameter in options: search_path`. The
  production URL pointed at Neon's pooled host, and the ORM engine sent a `search_path` startup option the pooler
  rejects. The data pools (asyncpg) connect separately and weren't affected, which is why stats kept working.
- **Mitigation:** switched the production URL to the unpooled host; sign-in recovered.
- **Fix:** [#368](https://github.com/getcommunityone/open-navigator/pull/368) sends no startup option on a pooled host,
  with a unit test for both hosts, so the same URL change can't take sign-in down again
  ([#367](https://github.com/getcommunityone/open-navigator/issues/367)).
- **Lesson:** a health check that only proves "the API is up" missed this. The two database paths need their own
  checks; see [Not built yet](#not-built-yet).

</details>

## Not built yet

These are the DataOps pieces a larger platform needs that this repo doesn't have today:

- **Escalation and paging:** failures are logged and visible on the admin dashboard, but nothing pages an on-call
  person.
- **Downstream notification:** users of a table aren't told when its refresh fails or is late. The national stats
  stayed on a June snapshot for months ([#291](https://github.com/getcommunityone/open-navigator/issues/291)).
- **Learned anomaly detection:** data quality checks are rule-based dbt tests. Nothing models expected volumes or
  distributions and flags drift.
- **AI root-cause assessment:** failures are classified by type for retry, but no agent reads logs to propose a cause
  or a fix.
- **Health checks per dependency:** `/api/health` reports the process only, not the ORM and data connections
  separately (the gap behind incident 2).
