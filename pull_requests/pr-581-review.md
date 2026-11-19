---
pr: 581
branch: fix/359-keep-unembedded-sidecars
title: "fix(llm): only delete caption_formatted sidecars the transcript already embeds"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(llm): only delete caption_formatted sidecars the transcript already embeds

## Summary
`remove_redundant_transcript_files` used to unlink every `*.caption_formatted.json` sidecar without looking at the
main transcript. The PR reads the transcript once and deletes a formatted sidecar only when the transcript has a
non-empty `caption_formatted` of its own. Otherwise it keeps the sidecar and counts it as `kept_formatted_sidecar`. An
unreadable or non-object transcript now keeps its sidecars. The change is small and works as described: I
reproduced the three new tests, and the two keep-tests fail on the old function. The one gap is that "non-empty"
is weaker than the issue's "equivalent", so a transcript whose embedded copy differs from the sidecar still loses
the sidecar. The PR body names this choice, and in practice nothing writes an embedded `caption_formatted`.
Verdict: approve-with-nits.

## Scope of Change
- Files changed: 2 (+91 / -18, excluding generated files; none touched)
- Areas touched: packages (`llm`), tests
- Commits:
  - `8089efff` fix(llm): only delete caption_formatted sidecars the transcript already embeds
- Range reviewed: `0ba4fcd2..8089efff` (`git merge-base origin/main origin/fix/359-keep-unembedded-sidecars`..HEAD; base branch is `main`, not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required, no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No credentials, tokens or URLs in the diff.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/` change. Test fixtures use obvious text (`"only copy"`).
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. The change makes deletion stricter, not broader: formatted
  sidecars are deleted in fewer cases than before. Nothing touches `data/cache/` by itself. I counted
  `*.caption_formatted.json` files under the local `data/cache/`: 0, so the change affects no existing file there.

## Strengths
- The fix follows the issue's Problem and the existing raw-sidecar check, and the transcript is read once and shared by both checks.
- Failure modes fail safe. A transcript that can't be read keeps its sidecars. Before, the formatted sidecar was
  deleted *before* the transcript was read at all, so an unreadable transcript lost its sidecar.
- A non-object JSON transcript used to raise `AttributeError` and abort the whole cleanup. It is now counted as `skipped_read_error` (verified by running it: `[1,2]` → `skipped_read_error: 1`, sidecar kept).
- Real regression tests. With `transcript_cache_paths.py` reverted to the base commit,
  `test_formatted_sidecar_is_kept_when_the_transcript_does_not_embed_it` and
  `test_formatted_sidecar_is_kept_when_the_transcript_cannot_be_read` fail; the "removed when embedded" test passes
  on both, as it should. Dry run and real run are both covered.
- Existing stats keys (`removed_formatted`, `would_remove_formatted`) keep their meaning, and `cleanup_policy_transcript_cache_tree` forwards the new key as `sidecars_kept_formatted_sidecar` with no change.
- Conventional commit with co-author trailer; branch `fix/359-…`; body says `Closes #359`; #359 has Problem, Done when, Contract and Read first.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`packages/llm/src/llm/gemini/transcript_cache_paths.py:2498-2499`: "non-empty" is not "equivalent", so a sidecar whose content differs is still deleted.** #359's Done-when says the sidecar is deleted "only when the transcript JSON embeds *equivalent* formatted captions". The code checks only `bool(data.get("caption_formatted"))`. *Verified:* in a scratch cache, `b.json` with `{"caption_formatted": [{"t": "different"}]}` and `b_.caption_formatted.json` containing `[{"t": "orig"}]` → the sidecar is removed (`removed_formatted: 1`) and the original content is lost. The PR body flags this choice and offers to be stricter. Risk today is low (see nit 2: no current writer embeds this key), but it is the same data-loss class as the issue. *Fix:* compare `json.loads(sidecar)` with the embedded value (or require the embedded payload to be a superset), and keep and count the sidecar when they differ. Or record in the issue why "non-empty" is accepted, as a dated line.

### 🔵 Nits / suggestions (Minor)
2. **The formatted-sidecar cleanup is now effectively dead, and the docs still say it deletes them.** `cleanup_policy_transcript_cache.py:7` ("Delete legacy `*.caption_formatted.json` duplicates") and the function docstring (`transcript_cache_paths.py:2446-2449`, "when the main transcript JSON already holds (or should hold) that payload") are stale. *Verified:* every writer strips `caption_formatted` from the main JSON (`load_youtube_events_to_postgres.py:2678`, `backfill_jurisdiction_transcripts.py:715`), and `write_policy_transcript_cache` never writes it. So no transcript will have the embedded key, and legacy formatted sidecars will now all be kept and counted. That is the safe outcome and what the issue asks for, but the module docs should say so, and someone should decide whether legacy formatted sidecars are ever to be removed (for example by the equivalence check in finding 1). Consider an `action-item` issue for that decision.
3. **Test gaps (small).** No test for: the legacy `…_.caption_formatted.json` name; a non-dict transcript (the `AttributeError` fix, which I only checked by hand); a transcript that embeds a non-empty value of another type (`str`/`dict`); a sidecar beside a raw sidecar in the same pass. In `test_formatted_sidecar_is_kept_when_the_transcript_cannot_be_read`, the last assertion `(tmp_path / DIR_TRANSCRIPTS).is_dir()` is always true and adds nothing.
4. **`transcript_cache_paths.py:2499`: `isinstance(embedded_formatted, (list, dict, str))` after `bool(...)` is redundant guard noise** (`5` and `True` would be rejected, which is fine). A short comment saying which shapes count as "embedded" would help.
5. **Stats name.** #359's Contract suggested a `*_sidecar` pattern such as `kept_sidecar`; the PR uses `kept_formatted_sidecar`. Consistent with `kept_orphan_sidecar` and clearer, so fine. Noting it only because the Contract's name list is what other layers may rely on.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/359-keep-unembedded-sidecars`; `Closes #359`; the issue has all four parts and the `bug` + `action-item` labels |
| Conventional Commits | Yes | `fix(llm): …` with co-author trailer |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | Edit in `packages/llm`; nothing added to `scripts/` |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | Partial | Module and function docstrings now overstate what is deleted (nit 2); no new docs files |
| Telemetry and logging | n/a | Pure function returning stats; the CLI logs them with loguru |
| Tests | Yes, with nit 3 | Two of the three new tests fail without the fix |
| Shared libraries | Yes | `packages/llm` tests ran (237 passed). The only callers are `cleanup_policy_transcript_cache.py` and `cleanup_policy_transcript_cache_tree`, both in the same package; there are no dependents in `api/` or other packages |

## Test Coverage
- **Run locally** (worktree code forced via `PYTHONPATH`): `pytest tests/test_policy_transcript_cache.py packages/llm/tests -q` → 237 passed.
- **Revert check:** `transcript_cache_paths.py` reset to the base commit → 2 failed, 6 passed (the two keep-tests fail, as the PR claims). Restored with `git checkout HEAD --`.
- **Ruff:** `ruff check` on the two changed files reports one error, E402 at `transcript_cache_paths.py:66`. It is in the import block, not in a line this PR touched, which matches the PR body ("on `main`, not from this change").
- **Not run:** dbt, frontend, API (not touched).
- **PR-body claims:** "13 pass" was not reproduced as a count (I ran the larger set; all pass). "The two keep-tests fail on the old function and pass on the fix" is confirmed.

## Verdict
**approve-with-nits.** The change fixes the bug in #359 and is safe, and CI is green. Before or shortly after merge, either tighten the check to real equivalence (finding 1) or write the "non-empty is enough" decision into #359. The docstring and test nits can follow in a small commit or an `action-item` issue.
