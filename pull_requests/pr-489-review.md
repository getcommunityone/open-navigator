---
pr: 489
branch: feat/297-colab-gpu-diarize
title: "feat(llm): run WhisperX diarization on Colab against the landing volume"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(llm): run WhisperX diarization on Colab against the landing volume

## Summary
The PR adds `llm.gpu.colab_diarize` (`python -m llm.gpu.colab_diarize`), a capped, resumable WhisperX
batch against the Databricks landing volume (Files API, Google Drive fallback), plus shared helpers in
`llm.gpu.diarize_common`, a thin Colab notebook, and deployment docs that point runs at Colab per the
GPU decision page. The design is sound: explicit owner yes, token redaction, honest CU estimates,
per-item write-before-next for resume, and Modal kept with re-exports so its tests stay green.
**Merge state is `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY` against current `main`.** A
read-only `git merge-tree` shows one conflict, in `.gitignore`: `main` has
`!notebooks/colab_gemma_policy_analysis.ipynb` and this branch has `!notebooks/colab_gpu_diarize.ipynb`
on the same line. Both exception lines are needed; the author must rebase or merge and keep both
before this can land. One should-fix remains: a result with `diarization_error` is stored as `ok` and
skipped on resume.

## Scope of Change
- Files changed: 10 (+1,261 / -113) for the feature commits; the prior review file on the branch is
  overwritten by this review (not counted in the +1,261)
- Areas touched: packages (llm) / web_docs / notebooks / tests / .gitignore
- Commits:
  - `76b66a22` refactor(llm): share the WhisperX runner's plain helpers in llm.gpu.diarize_common
  - `a83c944f` feat(llm): run WhisperX diarization on Colab against the landing volume
  - `0ff1bc82` docs(web_docs): make Colab the documented path for GPU diarization
  - `a79b059b` docs(review): PR #489 review (prior written review; superseded by this file)
- Range reviewed: `ea026669..a79b059b` (merge base with `main`; PR base is `main`, not stacked).
  Substance of the change is `ea026669..0ff1bc82`.

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success (on `0ff1bc82`) |
| Documentation Build (Docusaurus) | success (on `0ff1bc82`) |
| Backend Tests (Python) | success (on `0ff1bc82`) |
| API Types (OpenAPI -> TypeScript) | success (on `0ff1bc82`) |
| PR conventions (linked issue) | success (on `0ff1bc82`) |
| Detect Docker-relevant changes | success (on `0ff1bc82`) |
| Docker Build Test (Full Stack) | skipped (not required) |

Required checks are green on the last feature commit `0ff1bc82`. Current PR head
`a79b059b` (prior review commit only) reports no check rollup. CI does not include current `main`, so
it says nothing about the merge conflict.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Tokens come from Colab secrets or the environment; docs use a placeholder host
  (`dbc-xxxx…`); the notebook prints only "set"/"missing"; every code cell has empty `outputs` and
  `execution_count: null`. Test strings (`hf_SuperSecretValue123`, `dapiSECRET0000`) are fixtures only.
  `redact()` is covered by tests that capture stdout, stderr and loguru.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/` changes. CU rates (T4 1.76,
  L4 4.82, A100 11.77) and `$9.99/100 CU` are labelled estimates in usage rows; unknown GPUs get
  `None`. Docs' "~0.2 CU per meeting" recomputes from the stated 401 GPU seconds × 1.76 CU/h and is
  labelled as a Modal T4 estimate, not a Colab measurement.
- **Personal data:** clean. Public meeting audio/transcripts; usage rows hold item paths and GPU time.
- **Destructive or bulky data changes:** clean. No `data/cache/` deletes, no large dumps committed.
  Writes are new files under `diarized/<run_date>/`. PR claim that nothing was written to Databricks
  or Neon holds (no GPU run was started).

## Strengths
- Matches `AGENTS.md` GPU rules: Colab only, explicit yes checkbox in the notebook, usage before/after,
  cost to be pasted into the issue/PR.
- Resume is disconnect-safe: per-item result + usage write, `LocalStore` uses `.partial` then rename,
  `split_done` skips by output name.
- Path escape checks reject `..` and absolute paths outside the volume (tested with `/etc/passwd`).
- Refactor is behaviour-preserving: Modal re-exports the moved helpers; `IMAGE_PACKAGES ==
  WHISPERX_PACKAGES` is asserted; 254 local tests pass.
- New Python lives in `packages/llm` as `python -m llm.gpu.colab_diarize`; loguru; nothing added under
  `scripts/`. Docs are kebab-case under `web_docs/docs/` with frontmatter.

## Findings
### 🔴 Blocking (Critical)
None on the code itself. The PR **cannot merge** until the `.gitignore` conflict with `main` is
resolved (keep both notebook `!` exception lines). That is a merge blocker, not a logic defect.

### 🟡 Should fix (Important, non-blocking)
1. **A result with `diarization_error` is recorded as `ok` and then skipped on resume**
   (`packages/llm/src/llm/gpu/colab_diarize.py`, `run_batch` ~421–428).
   `diarize_audio_whisperx(..., allow_no_speakers=True)` keeps the ASR transcript and sets
   `diarization_error` when speaker separation fails (docstring: gated model refused). That is the
   likely first-run failure if the HF token has not accepted pyannote's conditions; `main()` only
   checks that a token exists. *Verified* with a stand-in diarize returning `diarization_error:
   "401 gated"`: row is `run_status_code: ok`, `speakers: 0`, exit code 0; `summary_table` does not
   mention the error; a second `run_batch` with the same item and run date returns `skipped`. A paid
   run that produced no speakers looks green and will not retry until the output is deleted. *Fix:*
   give such an item a distinct status (e.g. `ok_no_speakers` or `failed`) so resume does not treat it
   as done, surface the error in `summary_table`, and add a regression test (none covers this path).

### 🔵 Nits / suggestions (Minor)
1. **Output names can collide** (`diarize_common.output_name`). Extension is stripped, so
   `audio/a.opus` and `audio/a.mp3` both map to `audio_a.diarized.json`; URL hosts are dropped, so
   `https://x.org/m/516.mp4` and `https://y.org/m/516.mp4` collide. The second is skipped on resume.
   *Verified* by calling `output_name` on those pairs. Low risk for first runs; a docs note or hash
   suffix later is enough.
2. **A balance of exactly `0` is read as "not entered"** (`notebooks/colab_gpu_diarize.ipynb`, cells
   4 and 6: `cu_balance_before or None` / `cu_balance_after or None`; print uses `or 'not entered'`).
   If a run spends the last units, the measured row is skipped. Prefer an explicit empty default or
   `is None` check.
3. **CU rates are unverified offline.** Colab publishes no table; the PR and docs say so and label
   rows as estimates. The first real Colab measured CU row is the check. Note only.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | Branch `feat/297-colab-gpu-diarize`; body `Closes #297` with Attributes (epic #293, story #297); issue has Problem / Done when / Contract / Read first. Commits use `Refs #297`. PR conventions check passed on `0ff1bc82` |
| Conventional Commits | Pass | `refactor(llm)`, `feat(llm)`, `docs(web_docs)`; co-author trailers present |
| No fabricated data | Pass | See scans; estimates labelled; unknown GPU → `None` |
| New Python in `packages/` | Pass | `packages/llm/src/llm/gpu/`; CLI `python -m llm.gpu.colab_diarize`; nothing new in `scripts/` |
| dbt for transformations | N/A | No SQL/dbt |
| Naming | N/A | No warehouse columns |
| Keys | N/A | No `public` model |
| Calendar years | N/A | `run_date` is a full `YYYY-MM-DD` path segment, validated |
| Scope label matches filter | N/A | No UI |
| Match evidence on filtered tiles | N/A | No UI |
| Docs | Pass | `web_docs/docs/deployment/colab-gpu-diarize.md`; decision page gets a dated addendum, not a rewrite |
| Telemetry and logging | Pass | loguru in the package; no FastAPI work |
| Tests | Mostly | 21 new tests cover batch, resume, paths, usage/CU, redaction, Databricks store, notebook shape. Missing: `diarization_error` path (finding 1) |
| Shared libraries | Pass | Touched `packages/llm`; ran its tests plus Modal/Colab/gpu dependents below |

## Test Coverage
Run in worktree `/tmp/rev-489` with
`PYTHONPATH=$(ls -d $PWD/packages/*/src | tr '\n' ':')$PWD` and the main checkout's
`.venv/bin/python` (so editable installs do not pull the other tree):

`pytest tests/test_colab_diarize.py tests/test_modal_diarize.py tests/test_colab_bootstrap.py
tests/test_colab_runtime_phases.py tests/test_gpu_rules.py tests/test_diarize_pipeline_token.py
packages/llm/tests -q -p no:cacheprovider` → **254 passed**, matching the PR body.

`ruff check packages/llm/src/llm/gpu tests/test_colab_diarize.py` → clean.

The only consumer of the moved helpers is `modal_diarize` (and the workflow that invokes it by path),
covered by `tests/test_modal_diarize.py`. No frontend or dbt files changed; `tsc` and dbt were not
run. Local warehouse URL is set (`NEON_DATABASE_URL_DEV`); no read-only query was needed. No GPU,
Colab, Databricks or Modal run was attempted. WhisperX install on Colab's image remains unverified,
as the PR states.

**PR body claims:** the 254-test and ruff claims reproduce. Docs-build claim matches CI on
`0ff1bc82` (not re-run locally). "No GPU / volume / Neon write" holds. Issue Done when asks for docs
with **measured** GPU hours; the page gives a Modal T4 measurement labelled as Modal and says the
first Colab run will add the Colab figure — honest, but the Colab-measured figure is still missing
(unverified against the full Done-when line until that run).

## Verdict
**approve-with-nits.** The Colab path is the right shape and the local suite is green. Before merge:
resolve the `.gitignore` conflict with `main` (PR is `CONFLICTING` / `DIRTY`; keep both notebook
exceptions). Fix the `diarization_error` status (finding 1) before the first paid run — ideally in
this PR with a test — since a gated-model refusal is the failure mode most likely on first use. Nits
can follow.
