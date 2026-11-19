---
pr: 573
branch: feat/572-gemma-small-models
title: "feat(llm): add smaller Gemma 4 aliases, an attention flag and GPU memory logging"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(llm): add smaller Gemma 4 aliases, an attention flag and GPU memory logging

## Summary
The PR adds three small things to the Colab Gemma runner (`llm.gpu.colab_policy_analyze`): aliases for the E2B, E4B
and 12B models, an opt-in `--attn-implementation` flag that reaches `from_pretrained` only when given, and peak-GPU-memory
logging with an OOM log line. It also rewrites the Colab doc with the first pilot's measurements. The code does what
the issue's "Done when" asks: I ran the tests (all 32 in the file pass, and the 5 new cases fail on the old source),
the three repo ids exist on Hugging Face, and CI on the head commit is green. The generation, OOM and attention paths
were not run (no GPU, by instruction and by the PR's own statement). Nothing blocks the merge. The findings are about
the doc's numbers (one doesn't reproduce from the repo's own rate, one has no stated source), the Colab notebook not
exposing what the doc tells the owner to try next, and untested `from_pretrained` plumbing.

## Scope of Change
- Files changed: 3 (+125 / -23); no generated files
- Areas touched: packages (llm) / web_docs
- Commits:
  - `54b4cd95` feat(llm): add smaller Gemma 4 aliases, an attention flag and GPU memory logging; record pilot results
  - `729faeef` docs(web_docs): correct the pilot prompt sizes and add the bundle's token distribution
- Range reviewed: `0ba4fcd2..729faeef` (merge base with `main`; the PR's base is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Detect Docker-relevant changes | pass |
| Docker Build Test (Full Stack) | skipped (not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. A keyword scan of the diff hits only `hf_token` parameter names and the word "tokens"; no keys,
  credentials or cookies.
- **Fabricated data in a served path:** clean for `api/` and `web_app/` (not touched). The doc is not a served data
  path, but it states measurements as facts; findings 1 and 2 are about two of them that I could not reproduce.
- **Personal data:** clean. The doc names a video id (`Vs1PKup62NA`, a public meeting) and a laptop path under
  `data/cache/`; no personal information.
- **Destructive or bulky data changes:** clean. Nothing is deleted or committed in bulk; the doc only points at
  `data/cache/model_comparison/...` on the author's machine.

## Strengths
- The attention flag is genuinely opt-in: `kwargs["attn_implementation"]` is set only `if attn_implementation:`, so the
  default `from_pretrained` call is unchanged, as the issue requires.
- The aliases are built from one table and also register the lowercase repo id and the repo id without `google/`, so
  `resolve_model` (which lowercases its input) accepts all the spellings the issue lists. Existing aliases are
  untouched.
- The OOM branch re-raises, so `run_batch`'s per-meeting `except Exception` still marks the meeting failed and the batch
  continues.
- The doc is candid: it says answer quality was never scored, that the limit lies between 28,416 and 56,752 tokens,
  that "4 times the attention memory" is a guess, and that `sdpa` is untested. The arithmetic I could check is right
  (below).
- The new tests fail without the change (verified by reverting the source file to the merge base: 5 failed, 27 passed).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`web_docs/docs/deployment/colab-gemma-policy-analysis.md:167`: "About 2.3 units for the 26B meeting by GPU
   seconds" does not follow from the numbers beside it.** The doc gives 525 s on an A100, and the repo's own rate is
   `COLAB_CU_PER_HOUR["A100"] = 11.77` (`colab_io.py:32`), so \(525/3600 \times 11.77 = 1.72\) units, not 2.3.
   *Verified:* the calculation above. The "18.11 units over the two runs" figure is a correct difference
   (1889.42 − 1871.31), and "1.7 times faster" (9.4/5.6) and "16% faster" ((624 − 525)/624) also check out. *Fix:* give
   the figure the rate produces, or state the rate and the seconds the 2.3 comes from.
2. **`colab-gemma-policy-analysis.md:158`: the 31B row claims "about 5.6 tokens/s" while its Output tokens cell says
   "not kept".** A tokens-per-second figure needs the output token count (it would be about 3,500 tokens), and the doc
   says the 31B answer was lost. The "1.7 times faster per token" conclusion on line 163 rests on this figure. I could not
   find where it came from, and I can't reproduce it. *Fix:* say how the 5.6 was obtained (a logged line, a
   progress bar), or mark it as approximate and drop the ratio until the 31B output length is known.
3. **`notebooks/colab_gemma_policy_analysis.ipynb:139`: the notebook can't use what this PR adds.** The model form field
   is `#@param ["google/gemma-4-31B-it", "google/gemma-4-26B-A4B-it"]` (a fixed list) and `argv` (lines 149-155) never
   adds `--attn-implementation`. The doc (new "What is still not known") says "the next GPU run should try
   `--attn-implementation sdpa`", but the owner's only GPU path is this notebook, so that run would need the notebook
   edited first. *Verified:* read the cell; `cpa.main(argv)` builds its arguments only from those variables. *Fix:*
   add an `attn_implementation` field (`["", "sdpa", "eager", "flash_attention_2"]`, added to `argv` only when
   non-empty) and the three small aliases to the model list, or file an `action-item` issue and link it.
4. **`packages/llm/tests/test_colab_policy_analyze.py:407-426`: the plumbing the issue promises is untested.** The tests
   cover alias resolution and the parser. Nothing checks that `HFGemmaGenerator` passes `attn_implementation` to
   `from_pretrained` only when it is given, and nothing covers the OOM branch or the peak-memory log. The first is the
   issue's "default behaviour is unchanged" line. *Verified by reading:* nothing in the test file constructs `HFGemmaGenerator`
   (`grep` finds no mention of it), so the generator edits have no test that could fail. *Fix:* a test that fakes
   `AutoProcessor`/`AutoModelForImageTextToText` (monkeypatching, as the file already does for other parts) and asserts
   the kwargs with and without the flag; `torch` is installed in the repo venv, so an OOM test can raise
   `torch.cuda.OutOfMemoryError` from a stub `generate` on a CPU machine.

### 🔵 Nits / suggestions (Minor)
5. **`colab_policy_analyze.py:303-308`: `empty_cache()` runs while the failing frames are still alive, so it may free
   little.** The call sits inside the `except` block; the exception's traceback still references the `generate()` frames
   and their intermediates, and `inputs` is still bound. The cache can only release blocks nothing refers to. The
   existing handler in `run_batch` (`:587-596`) has the same shape. *Not verified:* this needs a CUDA run, so treat it as
   a risk, not a bug. If the next meeting still fails right after an OOM, move the `empty_cache()` after the `except`
   block has finished (for example in `run_batch` after the outcome is recorded, which already calls it), and say
   "may free" in the comment.
6. **`colab_policy_analyze.py:86`: the comment says the small models are "faster per token", but the doc (line 17) says
   their speed is not measured.** Reword the comment, since the doc's own pilot found the 26B mixture-of-experts model only
   1.7 times faster than the 31B.
7. **`choose_quantization` (`:125`) is size-blind, so `e2b`, `e4b` and `12b` go to 4-bit on any GPU under 70 GB.** Quantizing a
   2B-4B model to NF4 is rarely what's wanted, and the `llm_int8_skip_modules` list was written for the 31B/26B
   models. *Not verified:* whether those names cover the E-models' extra per-layer embeddings (no GPU run). The doc already
   says the small models are unmeasured; consider adding a line that they currently load in 4-bit under `--quantize
   auto`, so a pilot passes `--quantize none` deliberately.
8. **The PR body says `pytest` cannot collect on the author's machine and the tests were "called directly".** In a
   clean worktree here, `pytest packages/llm/tests/test_colab_policy_analyze.py` collects and passes (32 passed), as does
   the wider `-k "colab or gemma or compare_models or gpu"` selection (55 passed). The dangling symlink is the author's
   environment, not this change; CI's Backend Tests are green.
9. **Doc figures I could not check.** The bundle statistics (138 requests, median 56,570 tokens, the table of meetings
   under each limit, 28,403 vs 28,416 tokens, the `Gemma4UnifiedForConditionalGeneration` class for 12B) come from files
   or a model that are not in the repository, and the repo rules forbid reading `data/cache/` contents for review. The
   percentages are consistent with each other (25 of 138 is about 1 in 5.5, so "about 1 in 6" is fair). They are the
   author's measurements and are unverified here.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/572-gemma-small-models`; body says `Closes #572` and `Refs #569, #511`; #572 has Problem, Done when, Contract, Read first. A planned-work Attributes table isn't needed: the issue isn't tagged to a PI epic, and the PR conventions check passes |
| Conventional Commits | Yes | `feat(llm): …`, `docs(web_docs): …`, with the co-author trailer |
| No fabricated data | Yes, with findings 1-2 | No served path touched; two doc figures don't reproduce |
| New Python in `packages/` | Yes | Edits an existing `packages/llm` module; nothing added to `scripts/` |
| dbt for transformations | n/a | No SQL or dbt |
| Naming | n/a | |
| Keys | n/a | No tables |
| Calendar years | n/a | |
| Scope label matches filter | n/a | No UI |
| Match evidence on filtered tiles | n/a | No UI |
| Docs | Yes | Existing page under `web_docs/docs/deployment/`, frontmatter intact; the Documentation Build passes |
| Telemetry and logging | Yes | `loguru` for the new lines (`logger.error`/`logger.info`), as the package does elsewhere |
| Tests | Partial | New alias and parser tests fail without the change; the generator plumbing, OOM and memory log aren't tested (finding 4) |
| Shared libraries | Yes | `packages/llm` colab/gemma/compare_models/gpu tests: 55 passed, plus the touched file in full (32 passed) |
| GPU and paid compute | Yes | Nothing runs on a GPU; the doc asks for the owner's yes before the next run and records the cost of the last |

## Test Coverage
- **Run locally** (worktree code forced through `PYTHONPATH`, repo venv):
  - `pytest packages/llm/tests/test_colab_policy_analyze.py`: 32 passed.
  - `pytest packages/llm/tests -k "colab or gemma or compare_models or gpu"`: 55 passed (the dependents of the
    module: the Colab export and IO, the Gemma HF backend, `compare_models`).
  - Reverted `colab_policy_analyze.py` to the merge base: 5 of the new tests failed, the 27 older ones passed;
    restored with `git checkout`.
  - `ruff check` on the changed Python files: clean.
  - Hugging Face API: `google/gemma-4-12B-it`, `-E4B-it`, `-E2B-it` and `-31B-it` all return 200 (existence only, not
    whether the repos are gated).
- **Covered:** alias spellings (including the existing `31b`), the parser default, a valid and an invalid
  `--attn-implementation`.
- **Not covered, and not runnable here:** `from_pretrained` kwargs, peak-memory and OOM logging, `flash_attention_2`
  availability, and whether `sdpa` helps long prompts. The PR says the same.
- **Not run:** `tsc`, dbt and the web app: no frontend, API or dbt files changed.

## Verdict
**approve-with-nits.** Nothing blocks the merge: the code matches the issue, the new tests are real, and CI is green.
Before or soon after merging, fix findings 1 and 2 (two doc numbers that don't reproduce, one of which feeds the "1.7 times
faster" conclusion), and either wire the notebook (finding 3) or file the follow-up as an `action-item` issue. Add the
`HFGemmaGenerator` kwargs test (finding 4). The nits can follow.
