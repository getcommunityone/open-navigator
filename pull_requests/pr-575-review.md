---
pr: 575
branch: feat/574-colab-run-guards
title: "feat(llm): fail prompts that will not fit early and release the Colab runtime only once results are safe"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(llm): fail prompts that will not fit early and release the Colab runtime only once results are safe

## Summary
The PR adds a pure `check_prompt_fits(...)` that holds the context check plus a new opt-in `--max-input-tokens N`
cap, wired through `HFGemmaGenerator`, and a last notebook cell (8) that calls `runtime.unassign()` only when the
results are on the landing volume, a mounted Drive, or the owner ticks `results_copied_elsewhere`. The Python change
is small and correct: the flag is off by default, the old context message path is preserved, and the two new tests
fail on the base version of the source and pass on the head. The one real gap is that the notebook, which is how paid
runs are actually started, never passes the new flag, so the protection the PR is motivated by is only reachable from
the terminal. That and a few small points are non-blocking. **This is a stacked PR: its base is
`feat/572-gemma-small-models` (PR #573), not `main`, so the range is the merge base with that branch.** Verdict:
approve-with-nits.

## Scope of Change
- Files changed: 4 (+75 / -6; no generated files)
- Areas touched: packages (llm) / notebooks / web_docs
- Commits:
  - `621af934` feat(llm): fail prompts that will not fit early and release the Colab runtime only once results are safe
- Range reviewed: `729faeef..621af934` (`729faeef` = `git merge-base origin/feat/572-gemma-small-models origin/feat/574-colab-run-guards`; base branch confirmed with `gh pr view 575` as `feat/572-gemma-small-models`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | not run on this PR (base is not `main`; only the `PR conventions` workflow triggered) |
| Documentation Build | not run on this PR (same reason); a docs page changed, so it will run after the retarget to `main` |
| Backend Tests | not run on this PR (same reason); run locally: `packages/llm/tests` 238 passed |
| API Types | not run on this PR (same reason); no API change |
| PR conventions | pass (run 44443977008) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No keys, tokens or credentialed URLs in the diff. The notebook cell reads no secrets and prints
  none (it prints `store.label`, a volume or folder path).
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/`. The numbers in the flag help and
  the doc (28,416 fit, 56,752 did not) are the pilot measurements already in the doc's own tables (#569), not invented.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. Nothing deletes `data/cache/`; no data files or outputs are
  committed. The one destructive action, releasing the runtime, is the guarded cell 8 (see Strengths and Finding 2).

## Strengths
- Pure, testable check: the logic moved out of `generate()` into `check_prompt_fits`, and `generate()` calls it, so the
  tested function is the one that runs. Behaviour without the flag is unchanged (`None` skips the cap; the context
  message is the same text modulo the model id).
- Both failure modes raise `ContextTooLong`, which `analyze_request` already turns into a failed outcome with the
  reason and a `ContextTooLong` call record, so a capped meeting is recorded rather than crashing the batch, and no
  generation is attempted.
- Cell 8 fails safe: it refuses to release when results are only on the runtime disk, and `make_store()` can only
  return the landing volume or the Drive folder (it raises otherwise), so `on_volume or on_drive` is true for any
  store the run could have used.
- Issue-first is followed: branch `feat/574-colab-run-guards`, `Closes #574` / `Refs #569`, the issue has Problem,
  Done when, Contract and Read first, and the contract names match the code (`check_prompt_fits`, `--max-input-tokens`,
  `HFGemmaGenerator(..., max_input_tokens)`, cell 8 fields `release_runtime` and `results_copied_elsewhere`).
- The PR body says plainly what was not run (cell 8 in Colab, the flag on a real GPU).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`notebooks/colab_gemma_policy_analysis.ipynb` cell 5 (lines 149-154): the notebook has no way to set `--max-input-tokens`.**
   The PR is motivated by a full run on paid units failing most meetings with out-of-memory errors (25 of 138
   prompts are at most 28,500 tokens), and the notebook is the documented way to start that run. Cell 5 builds `argv`
   from `--videos-file --model --quantize --limit --run-date` (+ `--pilot`, `--cu-per-hour`) and nothing else, so a
   notebook user cannot turn the cap on; only the terminal command can. Same gap exists for `--attn-implementation`
   from the previous PR, so it is a pattern, not new. *Verified by:* reading cell 5 in full; there is no
   `max_input_tokens` form field. *Fix:* add a `max_input_tokens = 0  #@param {type:"integer"}` field (0 = off) and
   `if max_input_tokens: argv += ["--max-input-tokens", str(max_input_tokens)]`. If leaving it out is intentional,
   say so in the doc under step 5.

### 🔵 Nits / suggestions (Minor)
2. **`colab_policy_analyze.py:235`: `0` and negative values are not validated.** `if max_input_tokens and ...` treats `0`
   as "off", and a negative value is truthy, so `--max-input-tokens -1` fails every meeting after the model is loaded.
   *Verified by:* calling `check_prompt_fits(10, context_tokens=None, max_new_tokens=1, max_input_tokens=-1)` (raises)
   and `max_input_tokens=0` with a 1,000,000-token prompt (does not raise). *Fix:* use `type=positive_int` in argparse,
   or compare with `is not None` and reject values below 1.
3. **The cap is applied after the model is loaded and the prompt tokenized** (`run_batch` builds the generator at
   line 569, then `generate()` checks). With the flag a run whose prompts are all too long still pays for the model
   load before failing each meeting at once. The PR text ("fail ... at once", "no generation attempted") is accurate
   about generation, but not about the load. Low impact because the failure itself is cheap; a later improvement is
   to skip the model load when the bundle's token counts show nothing fits.
4. **Cell 8 releases right after the last write to a mounted Drive** (`notebooks/...ipynb` lines 212-224).
   Drive writes through the FUSE mount can be buffered, and `runtime.unassign()` right after may drop an unsynced
   file. `google.colab.drive.flush_and_unmount()` before `unassign()` is the usual guard. *Unverified:* I cannot run
   Colab here; this is from known Drive-mount behaviour, so treat it as a suggestion. Also `on_drive` is true for any
   mounted Drive even if this run's store is the landing volume (harmless, since the volume case is already safe).
5. **Test gap (minor).** `HFGemmaGenerator.__init__` storing `max_input_tokens` and `main()` passing `args.max_input_tokens`
   into the factory (lines 265, 802) are not covered; `generate()` needs torch and a model. The pure function and the
   flag parser are covered, which is where the logic is. A `main(..., --dry-run)` or a fake-generator test cannot reach
   it without a larger refactor, so this is only noted.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/574-colab-run-guards`; body has `Closes #574`; issue #574 has all four parts |
| Conventional Commits | Yes | `feat(llm): ...` with the `Co-authored-by: Cursor` trailer |
| No fabricated data | Yes | Only measured figures from #569 in help and doc |
| New Python in `packages/` | Yes | Change is in `packages/llm`; nothing added to `scripts/` |
| dbt for transformations | n/a | No dbt or SQL |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | No frontend |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | Existing page under `web_docs/docs/deployment/` updated (cell 8, the flag) |
| Telemetry and logging | Yes | Package code keeps `loguru`; no FastAPI work |
| Tests | Yes (with note) | New tests fail on the base source and pass on the head (below); cell 8 and the wiring are untested |
| Shared libraries | Yes | Ran all of `packages/llm/tests` (238 passed); nothing outside the module imports it (`llm.gemini.compare_models` only mentions it in a docstring) |
| GPU and paid compute (`AGENTS.md`) | Yes | No GPU run; the PR adds a guard against wasted paid units and does not start a run |

## Test Coverage
- `test_check_prompt_fits_applies_the_context_and_the_cap` covers: fits, cap boundary (28,416 under a 30,000 cap),
  over the cap, over the model context, and no cap with unknown context. `test_max_input_tokens_flag_defaults_to_off`
  covers the flag default and parsing.
- **Reverted the source to the base** (`git checkout 729faeef -- packages/llm/src/llm/gpu/colab_policy_analyze.py`):
  both new tests fail (`2 failed, 32 passed`); restored with `git checkout HEAD --`.
- Run locally in the worktree with the worktree's code on `PYTHONPATH`: `test_colab_policy_analyze.py` 34 passed;
  all of `packages/llm/tests` 238 passed; `ruff check` on the changed Python is clean; the notebook JSON loads and
  cell 8 is valid Python as written.
- PR body claim "`pytest` cannot collect on this machine (dangling symlink)" is specific to the author's machine; it
  collects and passes here. The claims "ruff clean" and "notebook JSON loads" reproduce.
- **Not verified:** cell 8 in Colab (`runtime.unassign()`, the Drive and volume branches) and the flag on a real GPU;
  the PR says the same. No GPU or Colab was used in this review.

## Verdict
**approve-with-nits.** Nothing blocks the merge into `feat/572-gemma-small-models`. Before the paid full run, expose the
cap in notebook cell 5 (Finding 1) so the guard can actually be used from the notebook. Findings 2 to 5 can be fixed in
this PR or left. Retarget to `main` after #573 merges and let the required checks run, since only `PR conventions` ran
on this stacked PR.
