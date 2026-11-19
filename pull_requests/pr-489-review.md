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
The PR adds `llm.gpu.colab_diarize` (`python -m llm.gpu.colab_diarize`), a capped, resumable WhisperX batch that reads
audio from the Databricks landing volume (Files API, Google Drive fallback), writes
`crawl/diarized/<run_date>/<name>.diarized.json`, and appends one usage row per item with an estimated Colab compute
unit (CU) figure plus a measured batch row. The Modal runner's plain helpers move into `llm.gpu.diarize_common`
(re-exported, so the Modal path and its tests are unchanged). A thin notebook and a docs page come with it. The code
is clean, tested without a GPU or network, honest about what is an estimate, and keeps the owner's "explicit yes per
run" rule in the notebook. One real gap: a result that carries `diarization_error` (the likely first-run failure,
a gated pyannote model refused) is recorded as `ok` and then skipped on resume. Everything else is nits.
**Merge state: `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY`** against current `main`. I did not resolve it; a
read-only `git merge-tree` shows one conflict, in `.gitignore` (the notebook's `!` exception line sits next to a line
added on `main`). The author must rebase or merge before this can land.

## Scope of Change
- Files changed: 10 (+1,261 / -113)
- Areas touched: packages (llm) / web_docs / notebooks / tests / .gitignore
- Commits:
  - `76b66a22` refactor(llm): share the WhisperX runner's plain helpers in llm.gpu.diarize_common
  - `a83c944f` feat(llm): run WhisperX diarization on Colab against the landing volume
  - `0ff1bc82` docs(web_docs): make Colab the documented path for GPU diarization
- Range reviewed: `ea026669..0ff1bc82` (merge base with `main`; the PR's base is `main`, not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required) |

CI is on the head commit `0ff1bc82`, which does not include the current `main`, so it says nothing about the merge.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Tokens are read from Colab secrets or the environment, never written into the repo. The docs show
  `https://dbc-xxxx.cloud.databricks.com` as a placeholder host. The notebook prints only "set" or "missing". The
  notebook has no saved outputs (checked in the JSON: every code cell `outputs == []`, `execution_count == null`).
  The one browser User-Agent string is the existing Modal constant, moved.
- **Fabricated data in a served path:** clean. Nothing in `api/` or `web_app/`. The CU rates (T4 1.76, L4 4.82, A100
  11.77 CU/hour) are hard-coded constants, but they sit in a batch module, are described as user-reported, and every
  row says `compute_units_source: estimate ...`; a GPU with no rate gets `None` rather than a guess (tested). The
  docs' "0.2 CU per meeting" re-computes correctly from the stated 401 GPU seconds and 1.76 CU/hour (0.111 h x 1.76 =
  0.196) and is labelled as an estimate from a Modal run.
- **Personal data:** clean. Public meeting audio and transcripts only; usage rows hold item names and GPU time.
- **Destructive or bulky data changes:** clean. Nothing deletes `data/cache/`. The run only writes new files under
  `diarized/<run_date>/` (upsert of that run's own outputs). No large files are committed. The PR says nothing was
  written to Databricks or Neon, and this holds (no run was started).

## Strengths
- Honest cost accounting: per-item rows are labelled estimates with the rate and its origin; the measured batch CU is
  a separate row (`is_estimated: false`, `row_kind: batch_measured_cu`), and a top-up between balances gives `None`.
- Resume is safe against disconnects: results and usage are written per item, `LocalStore` writes through a
  `.partial` file and renames, and `split_done` skips by output name.
- Path handling blocks escapes: `volume_rel` rejects `..` and paths outside the volume (tested with `/etc/passwd`).
- Tokens are redacted from error text and never logged or printed; a test captures stdout, stderr and loguru output.
- The refactor is behaviour-preserving: the Modal functions are re-exported, `modal_diarize` still builds its image
  from the same pins (a test asserts `md.IMAGE_PACKAGES == dc.WHISPERX_PACKAGES`), and the 254 tests pass.
- Matches the repo layout rules: new Python is in `packages/llm`, a `python -m` CLI, loguru logging, nothing new in
  `scripts/`. The docs page is in `web_docs/docs/deployment/` with frontmatter and kebab-case.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **A result with `diarization_error` is recorded as `ok` and then skipped on resume**
   (`packages/llm/src/llm/gpu/colab_diarize.py`, `run_batch`, the `try` block that writes `out_rel` and sets
   `"ok"`). `diarize_audio_whisperx(..., allow_no_speakers=True)` keeps the transcript and returns
   `diarization_error` when speaker separation fails (its docstring names "a gated model refused"). That is the
   most likely first-run failure here, since the HF token must have accepted pyannote's conditions and `main()` only
   checks that a token exists. Verified with a stand-in diarize function: the row is `run_status_code: ok`,
   `speakers: 0`, `diarization_error: '401 gated'`; `exit_code` is 0; and re-running the same item and run date gives
   `skipped`. So a paid run that produced no speakers looks green, the summary table does not show the error, and
   the owner has to delete the output by hand to retry. Fix: give such an item its own status (e.g.
   `ok_no_speakers`, or `failed`) so resume does not treat it as done, show the error in `summary_table`, and add a
   test (there is none for this path).

### 🔵 Nits / suggestions (Minor)
1. **Output names can collide, and the second item is silently "done"** (`diarize_common.output_name`, moved from
   Modal). The extension is stripped, so `audio/a.opus` and `audio/a.mp3` both map to `audio_a.diarized.json`; for
   URLs the host is dropped too, so `https://x.org/m/516.mp4` and `https://y.org/m/516.mp4` collide. The second is
   skipped on resume. Verified by reading the regexes and the test's expected names. Low risk for the first runs;
   worth a line in the docs or a hash suffix later.
2. **A balance of exactly 0 is read as "not entered"** (`notebooks/colab_gpu_diarize.ipynb`, cell 6:
   `cu_balance_after or None`; cell 4 does the same for the "before" value). If a run uses the last units, the
   measured row is skipped with "enter both balances". Use `None` as the form default or test for `is None`.
3. **The CU rates are unverified.** I could not check Colab's per-GPU rates offline (Colab publishes no table); the
   PR and docs say so and the rows are labelled estimates, so this is a note, not a defect. The first real run's
   measured CU row is the check.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | Branch `feat/297-colab-gpu-diarize`; body says `Closes #297`, with the Attributes table (epic #293, story #297); PR conventions check passed, so the issue has its four parts. Commits use `Refs #297` |
| Conventional Commits | Pass | `refactor(llm)`, `feat(llm)`, `docs(web_docs)`; co-author trailer present |
| No fabricated data | Pass | See scans; estimates labelled, unknown GPU gives `None` |
| New Python in `packages/` | Pass | `packages/llm/src/llm/gpu/`; CLI is `python -m llm.gpu.colab_diarize`; nothing added to `scripts/` |
| dbt for transformations | N/A | No SQL or dbt change |
| Naming | N/A | No warehouse columns |
| Keys | N/A | No `public` model |
| Calendar years | N/A | `run_date` is a full `YYYY-MM-DD` date in a path, validated |
| Scope label matches filter | N/A | No UI |
| Match evidence on filtered tiles | N/A | No UI |
| Docs | Pass | `web_docs/docs/deployment/colab-gpu-diarize.md`, kebab-case, frontmatter; the decision page gets a dated line instead of a rewrite; docs build green |
| Telemetry and logging | Pass | loguru in the package; no FastAPI work |
| Tests | Mostly | 21 tests for the new module cover batch cap, resume, paths, usage rows, CU, token redaction, the Databricks store and the notebook shape. Missing: the `diarization_error` path (finding 1) |
| Shared libraries | Pass | Touched `packages/llm`; ran its whole test folder plus the Modal and Colab tests (below) |

## Test Coverage
Run in a worktree at the PR head, with `PYTHONPATH` forcing the worktree's `packages/*/src`:
`pytest tests/test_colab_diarize.py tests/test_modal_diarize.py tests/test_colab_bootstrap.py
tests/test_colab_runtime_phases.py tests/test_gpu_rules.py tests/test_diarize_pipeline_token.py packages/llm/tests`:
**254 passed**, matching the PR body. `ruff check packages/llm/src/llm/gpu tests/test_colab_diarize.py`: all checks
passed. The only dependent of the moved helpers is `modal_diarize` (and the `gpu-diarize-modal.yml` workflow that
runs it by path), covered by `tests/test_modal_diarize.py`; the workflow itself was not run. The imports the Colab
install relies on (`llm.usage.*`, `llm.gemini.diarize_postprocess`) need only `loguru` at import time, so
`pip install --no-deps -e packages/llm` plus `loguru` should be enough; the real WhisperX install on Colab's image
is unverified, as the PR itself says. No GPU, Colab, Databricks or Modal run was done or attempted. The docs build was
not re-run locally; CI's is green. No frontend or dbt files changed, so `tsc` and dbt were not needed.

## Verdict
**approve-with-nits.** Nothing blocks the design. Before merge: resolve the `.gitignore` conflict with `main` (the PR
is `CONFLICTING` / `DIRTY`). Fix the `diarization_error` status (finding 1) before the first paid run, ideally in
this PR with a test, since the first real run is the one most likely to hit a gated-model refusal. The nits can
follow.
