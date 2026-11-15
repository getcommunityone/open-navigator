---
pr: 215
branch: fix/policy-cache-cleanup-idempotency
title: "fix(llm): make policy transcript cache date and sidecar cleanup idempotent (#48)"
author: BlueHopper6
reviewed_at: 2026-11-13
reviewer: read-only reviewer subagent + coordinator verification (experiments re-run on throwaway trees)
verdict: request-changes
---

# PR Review: fix(llm): make policy transcript cache date and sidecar cleanup idempotent (#48)

## Summary

The fix for issue #48 works: a second cleanup run reports 0 moves, and names like `*.diagrams.diagrams.md` heal to
`*.diagrams.md`. But the healing introduces a new way to lose cache files. When two different files now map to the
same name, `_safe_move` keeps the one with the newer modification time and deletes the other, without comparing
contents and without logging it. Caption sidecars can be lost the same way, and the dry run doesn't predict it. On
main, the same files only got longer names and all survived. `CLAUDE.md` forbids losing anything under `data/cache/`,
so the verdict is request-changes. The fix is contained: delete only byte-identical duplicates, keep differing files
side by side, and count, log and test every collision.

## Scope of Change

- Files changed (against main after merging it in): 3 (+524 / -115)
  - `packages/llm/src/llm/gemini/transcript_cache_paths.py`
  - `tests/test_policy_transcript_cache.py`
  - `tests/test_meeting_date_from_title.py`
- Areas touched: packages (llm), tests
- Commits: b4eed29 fix(llm): make policy transcript cache date and sidecar cleanup idempotent; f998ab99 fix(web): resolve
  TypeScript CI errors (superseded: the merge keeps main's web files); baca6cd chore(llm): merge main into the branch
- Range reviewed: `origin/main...baca6cd`

## CI Status

| Check | Status |
|---|---|
| Required checks on f998ab99 (Nov 2) | all success |
| Required checks on baca6cd (the merge) | running at review time |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/` change.
- **Personal data:** clean. The tests use synthetic titles and ids.
- **Destructive data changes: fail.** The change adds new silent deletions of individual files under
  `data/cache/gemini_transcript_policy/` (findings 1 and 2).

## Strengths

- The root-cause analysis is careful and right: compound suffixes compounding, sidecars processed as transcripts, an
  unscoped `_lookup_run_meta`, and date validation.
- Idempotency holds in every scenario tried: pass 2 and pass 3 report 0 moves.
- The tests catch the original bug. 43 pass on this branch, and 3 of the new tests fail against main's old code
  (re-run by the coordinator).

## Findings

### 🔴 Blocking (Critical)

1. **Healing a name can delete a different file, chosen by modification time alone.**
   - Where: `transcript_cache_paths.py`, `_safe_move` (the `src.unlink()` / `dest.unlink()` branch), now reached through
     the new suffix normalisation and `_policy_file_dest`.
   - What happens: `X.diagrams.md` and `X.diagrams.diagrams.md` now map to the same destination, and the file with the
     older modification time is deleted whatever its contents. A modification-time tie (`<=`) deletes the source.
   - Verified: a clean file ("CLEAN-OLD") and a doubled one ("DOUBLED-NEWER", newer). Pass 1 left only the newer;
     with the times swapped it reported `dates_removed_older_duplicate: 1` and left only the other. On main both
     files survive.
   - The same applies to caption sidecars. A transcript whose captions live only in its sidecar lost that sidecar
     ("SRC-SIDECAR") to an existing, newer sidecar at the target. The sidecar branch counts only `moved`, so the
     deletion wasn't counted or logged.
   - Fix: delete only when the two files are byte-identical (compare SHA-256). Otherwise keep both: leave the source
     in place, or move it to `<name>.dup-<sha8><suffix>`, and count it as `skipped_collision`. Count and log every
     action `_safe_move` returns, including `removed_older_duplicate`.
2. **Two different meetings that map to the same name lose one file (existing behaviour, not fixed here).**
   - Verified: two transcripts with different `video_id`s, the same title "Council Meeting 04.28.26" and different
     upload dates both map to `2026-04-28_Council_Meeting.json`. The older one is deleted. Main behaves the same.
   - Fix: include the `video_id` (or another real discriminator) in the destination when two sources collide, or skip
     the collision as in finding 1. If kept out of this PR, it needs its own issue. In either case it needs a test.

### 🟡 Should fix (Important, non-blocking)

3. **The dry run under-reports deletions.**
   - When two sources collapse to a destination that doesn't exist yet, the dry run reports `would_move: 2`. The real
     run does 1 move and 1 deletion.
   - Fix: track the destinations already claimed during the dry run, or group sources by destination first as
     `migrate_policy_cache_layout` does.
4. **Test gaps.**
   - The idempotency test's doubled file has no clean sibling, so the data-loss path is untested.
   - No test covers a sidecar target collision.
   - No test covers `_lookup_run_meta` with another meeting's meta file present (the stricter lookup the PR
     describes).

### 🔵 Nits / suggestions (Minor)

5. `remove_redundant_transcript_files` deletes `.caption_formatted.json` without checking that the transcript embeds
   it. This is outside the diff: a follow-up issue.
6. The `"replaced_newer"` check in the sidecar branch can never match, because `_safe_move` returns `"moved"` after
   replacing. It is dead code, and part of the miscount in finding 1.
7. The new code logs no moves or deletions (`CLAUDE.md`: `loguru` in packages).

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partly | The description says "Fixes #48". The branch predates the `<type>/<issue>-<slug>` rule (#225). |
| Conventional Commits | Pass | `fix(llm)`, `fix(web)`, `chore(llm)` |
| No fabricated data | Pass | |
| New Python in `packages/` | Pass | |
| Never delete `data/cache/` | **Fail** | Findings 1 and 2 |
| Telemetry and logging | Fail (partly) | Moves and deletions aren't logged (finding 7) |
| Tests | Partly | 43 pass. The data-loss and collision paths are untested (finding 4) |
| Shared libraries | Partly | The `llm` tests pass. Dependents' tests weren't run. |
| Others (dbt, naming, keys, years, UI rules, docs) | N/A | |

## Test Coverage

Run locally: `pytest tests/test_meeting_date_from_title.py tests/test_policy_transcript_cache.py
tests/test_transcript_cache_geography.py` gives 43 passed on this branch; 3 fail against main's old code. Collision
experiments on throwaway trees (never a real `data/cache`) reproduced findings 1 to 3.

## Verdict

Request-changes. Keep the idempotency fix. Before merging: make `_safe_move` and the sidecar branch never delete a
file that isn't byte-identical, count and log every removal, make the dry run predict collisions, and add the
collision tests (findings 1 to 4). Finding 2 may move to its own issue.

## Re-review, 2026-11-15 (coordinator, after the maintainer's follow-up commits)

**Verdict: approve.** Merged `main` into the branch (68e46cbb) and fixed the findings in e031146d (`fix(llm): the date cleanup deletes a file only when it is byte-identical`).

| Finding | Status |
|---|---|
| 1. Healing a name deletes a different file by mtime | **Fixed.** New `_safe_policy_move` (used by `fix_policy_cache_dates_from_title` for files and sidecars) deletes the source only when the destination's SHA-256 matches; otherwise both are kept, counted as `skipped_collision` and logged with a warning. `_safe_move` is unchanged for `migrate_policy_cache_layout`, whose newest-wins collapse of legacy runs is intentional. |
| 2. Two meetings mapping to one name lose one | **Fixed by the same rule.** Different content means a skipped collision; both files survive. Test added. |
| 3. Dry run under-reports deletions | **Fixed.** The pass tracks claimed destinations, so the dry run reports `would_skip_collision` where the real run hits one. Test asserts dry and real counts match. |
| 4. Test gaps | **Fixed** for clean + doubled sibling (different and identical bytes), sidecar target collision, two meetings, and dry-run parity: `packages/llm/tests/test_policy_cache_cleanup_collisions.py` (5 tests; all 5 fail on the pre-fix head, pass now). The `_lookup_run_meta` case is not covered yet. |
| 5. `remove_redundant_transcript_files` deletes `.caption_formatted.json` unchecked | Out of scope; filed as #359. |
| 6. Dead `"replaced_newer"` check | **Removed;** every sidecar action is now counted as `<action>_sidecar`. |
| 7. No logging | **Fixed:** every move, deletion and collision is logged with `loguru`. |

**Merge with #347:** this branch's `_split_policy_filename_stem_and_suffix` replaces #347's `_strip_policy_suffix`; #347's regression tests (including caption sidecars never merging into their transcript) pass.

**Tests:** `packages/llm/tests` + `tests/test_meeting_date_from_title.py`, `tests/test_policy_transcript_cache.py`, `tests/test_transcript_cache_geography.py`: 226 passed, 2 failed (`test_meeting_gap_analysis.py`, same failures on `main`). `ruff` clean on the new test file.

**Minor, not blocking:** `_split_policy_filename_stem_and_suffix` also strips a trailing `_diagrams` / `_meta` from a stem, so a meeting title ending in "meta" would lose it. Rare; noted here.

**Before the first real run:** `python -m llm.gemini.cleanup_policy_transcript_cache --dry-run` twice on the real cache; the second run should report ~0 moves. Any `skipped_collision` lines in the log need a person to look at them.
