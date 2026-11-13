---
pr: 273
branch: ccr-87f694c6-ky2mfv
title: "feat(llm): track LLM and GPU usage, cut transcript-analysis cost, add Batch API and model comparison"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: two read-only subagents (python-packages-specialist for packages/, data-dbt-specialist for dbt and the migration) and the coordinator; every finding reproduced before it was written down
verdict: approve-with-nits
---

# PR Review: feat(llm): track LLM and GPU usage, cut transcript-analysis cost, add Batch API and model comparison

## Summary

The PR records token usage, latency and retries for every model call and GPU use for every GPU step, then uses those
numbers to make each transcript-analysis call cheaper. It adds a Batch API runner for the backlog, a model-comparison
CLI, and a field-size tool. It also fixes the hard-coded Tuscaloosa jurisdiction in the Part 1 prompt and models the
usage tables in dbt.

The first review pass found one Important defect: usage labels were lost in worker threads, so Demo 3 calls were
logged as `governance`. It also found four Minor ones in batch collect and the loader. All five are fixed in
15de2c2, each with a regression test.

What remains is minor: the branch name and one-PR-for-eight-issues deviation, which is explained in the description,
and the work that needs the warehouse, which hasn't run. Verdict: **approve-with-nits**.

## Scope of Change

- Files changed: 40 (+5,234 / -225)
- Areas touched: packages (llm), dbt_project, packages/hosting (migration), prompts, web_docs, pull_requests
- Commits:
  - 27ebbb8 feat(llm): record token usage, latency and retries for every model call, and GPU use for every GPU step
  - 9781bd9 perf(llm): cut the cost and latency of each transcript-analysis call
  - b14c4d2 chore(llm): lint fixes in the usage package and its tests
  - 069c067 feat(llm): run the transcript backlog through the Gemini Batch API
  - 798f6f2 feat(llm): compare models on the transcript analysis, with Gemma and Gemini 3.x arms
  - 4b9a179 fix(llm): score answers wrapped in a one-element array, and record the Gemma 26B result
  - ec47cf7 fix(llm): name each meeting's own jurisdiction in the Part 1 prompt, not Tuscaloosa
  - fb42a78 feat(llm): record the governance pipeline's Gemini calls, and model the usage tables in dbt
  - 95f098d feat(llm): measure which Part 1 fields take the output tokens
  - 09b4ee7 docs(llm): record the decision to keep speaker_segments and evidence_metrics in Part 1
  - bde7898 chore(llm): lint fixes from the pre-PR checks
  - 15de2c2 fix(llm): review fixes for usage labels in threads, batch collect and the loader
- Range reviewed: `origin/main..15de2c2` (merge base 55db346)

## CI Status

Status on bde7898, the head before the review fixes. A new run started on 15de2c2.

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | ✅ success |
| Documentation Build (Docusaurus) | ✅ success |
| Backend Tests (Python) | ✅ success |
| API Types (OpenAPI -> TypeScript) | ✅ success |
| PR conventions (linked issue) | ✅ success |
| Docker Build Test | skipped (no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. No key, token, password or credentialed URL is added.
- **Fabricated data in a served path:** clean. No file under `api/` or `web_app/` changes. Token counts stay null
  when the API doesn't report them. A cost is computed only from a price with a source and a read date in
  `prices.yaml`, and the Gemini rates there name their source (getdeploying.com, read 2026-11-13; confirming against
  Google is #266).
- **Personal data:** clean. Only the known labels (`stage`, `video_id`, `jurisdiction_id`, `api_mode`) reach the
  usage log, never prompt or transcript text.
- **Destructive or bulky data changes:** clean. Nothing is deleted. Usage logs go to the git-ignored `data/logs/`,
  and the new bronze tables come from a migration and are modelled in dbt.

## Strengths

- **Usage logging can never break a call.** Every recording path catches its own errors. A failed call is recorded
  with its latency and attempts, which is what the retries cost.
- **Batch and interactive runs produce the same files.** Both share `prepare_part1_request` and
  `save_part1_response`.
- **Migration, loader and staging agree.** The migration, `load_bronze` and the staging casts match column for column
  and type for type. Staging builds empty and typed until bronze exists, following the `stg_ordinances` pattern.
- **Cost is derived, never stored.** A corrected price reprices history, and an unsourced price yields no number at
  all.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

- **Fixed in 15de2c2: usage labels lost in worker threads.**
  - Where: `packages/llm/src/llm/governance/genai_quota_retry.py` (`call_with_wall_clock_timeout`) and
    `gatekeeper_triage.py` (the gatekeeper's `pool.submit`).
  - What: the `llm_call_context` ContextVar is not copied into a `ThreadPoolExecutor` thread. Demo 3, which uses the
    wall-clock timeout by default, was therefore logged as `governance`.
  - Verified: inside `llm_call_context(stage="demo3")`, the worker thread saw `{}`.
  - Fix: both pools submit through `contextvars.copy_context().run`. Test:
    `test_labels_reach_a_call_run_in_a_worker_thread`.

### 🔵 Nits / suggestions (Minor)

- **Fixed: `JOB_STATE_PARTIALLY_SUCCEEDED` never collected.**
  - Where: `batch_backlog.py`.
  - What: the state exists in google-genai 3.3.0's `JobState`, but `collect` treated it as not ready forever, and
    its videos stayed blocked from `submit`.
  - Fix: `ENDED_WITH_RESULTS`. Test: `test_partially_succeeded_jobs_have_results`.
- **Fixed: re-running `collect` after a crash recorded failures twice.**
  - Where: `batch_backlog.py` (`collect_results`).
  - Fix: outcomes are now written to the manifest as each video is collected, and videos already in it are skipped.
    A video analyzed meanwhile still gets its billed batch usage recorded.
  - Test: `test_collect_reports_progress_and_a_rerun_writes_nothing_twice`.
- **Fixed: `--no-persist-bronze` still stamped policy events.** It now sets `no_db_events`. Test:
  `test_no_persist_bronze_skips_every_database_write`.
- **Fixed: missing migration file gave a vague error.**
  - Where: `load_bronze.py`.
  - What: a missing file only logged a warning, and the insert then failed with "relation does not exist".
  - Fix: it now stops with the path.
- **Fixed: no direct test for the `process_one_video` split.** Added `test_process_one_video.py`, covering the model
  call arguments, saved usage, the transcript-only branch and the skip.
- **Open: branch name.**
  - What: `ccr-87f694c6-ky2mfv` isn't `<type>/<issue>-<slug>`, and one PR closes five issues and refers to three.
  - Why: the session can only push its own branch, as the description explains. The commits are per issue.
  - Status: the PR conventions check passed, because it applies from 2026-11-14.
- **Open: dbt test syntax.**
  - Where: `_schema_stg_llm_usage.yml` and `_schema_llm_usage_daily.yml`.
  - What: generic tests use the form without an `arguments:` block, which adds to dbt's deprecation warnings.
  - Status: cosmetic, and the same form is used elsewhere in the repo (`_schema_tags.yml`).

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partly | Issues #262–#269 each have the four parts. The branch name and the one-issue-one-PR rule are not followed (see the nit above). Follow-ups are their own issues. |
| Conventional Commits | ✅ | All 12 commits, each with the co-author trailer |
| No fabricated data | ✅ | Scan clean |
| New Python in `packages/` | ✅ | The new CLIs are `python -m llm.usage.report`, `llm.usage.load_bronze`, `llm.gemini.batch_backlog`, `llm.gemini.compare_models` and `llm.gemini.part1_field_sizes`. Nothing is added to `scripts/`. |
| dbt for transformations | ✅ | The daily rollup is in dbt. Python only loads JSONL into bronze. |
| Naming | ✅ | `llm_usage_daily`, `stg_llm__*`; no `dim_`/`fact_`. `fetch_videos` reads both `state_code` and `state`. |
| Keys | ✅ | `llm_usage_daily` declares PK (`usage_date`, `model`, `api_mode`). Not published to `public`, so no FKs are needed. |
| Calendar years | n/a | `usage_date` is a real `date` |
| Scope label / match evidence | n/a | No UI changes |
| Docs | ✅ | `web_docs/docs/development/llm-usage-tracking.md` and `transcript-analysis-cost.md`, kebab-case, with frontmatter |
| Telemetry and logging | ✅ | Package code logs with loguru (stdlib `logging` in `gemma_hf_backend.py`, as that module already did) |
| Tests | ✅ | Every behaviour change and each review fix has a test |
| Shared libraries | ✅ | `packages/llm` tests and the `tests/` files that import `llm` were run |

## Test Coverage

Run locally on 15de2c2:

- `pytest packages/llm` with the `tests/` files that import `llm` (`test_transcript_cache_geography`,
  `test_legislation_analysis`, `test_mermaid_diagrams`, `test_pipeline_media_scope`, `test_colab_runtime_phases`,
  `test_colab_bootstrap`, `test_meeting_date_from_title`, `test_meeting_consolidated_summary`): **267 passed**.
- CI's backend steps in a fresh environment: `pip install -r requirements.txt`, the editable packages, `py_compile`,
  `import main` and `from api.app import app`. All succeed.
- `web_docs`: `npm ci && npm run build` succeeds.
- `dbt parse` and `dbt ls` succeed for the new sources and models. `dbt build` was not run: the warehouse is not
  reachable from the session.
- `ruff check`: clean on the new files. The remaining findings in existing files predate the branch.

Not run, because each needs the warehouse or real transcripts (tracked in #267 and #269):

- `batch_backlog submit` selecting pending videos from the warehouse
- `load_bronze` inserts
- `fetch_videos` with the four new columns
- the model comparison and the field-size measurement on real meetings

## Verdict

**approve-with-nits.** The Important and Minor findings from the first pass are fixed on the branch with tests. No
🔴 findings. Merge once the required checks are green on 15de2c2 and the maintainer accepts the branch-name deviation.
