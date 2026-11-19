---
pr: 571
branch: feat/570-colab-notebook-defaults
title: "feat(llm): default the Colab policy notebook's bundle date and skip the Drive popup"
author: jcbowyer
reviewed_at: 2026-11-19
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(llm): default the Colab policy notebook's bundle date and skip the Drive popup

## Summary
The PR gives the Colab policy notebook two small defaults: a blank `export_date` resolves to the newest dated
folder under `policy_export/` via a new pure helper `colab_io.latest_child`, and cell 3 skips `drive.mount` when
that folder is already on the runtime. The paid-compute gate stays `False`, and the lookup runs after it. The
helper and its unit test work; the full `packages/llm` suite and CI are green. Two non-blocking gaps remain:
`latest_child` can pick a dated *file* or a Drive-style duplicate folder name, and the runbook still describes the
old form boxes. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 3 (+29 / -4) for the feature; this review file is rewritten on the branch
- Areas touched: packages (llm), notebooks
- Commits:
  - `86253610` feat(llm): default the Colab policy notebook's bundle date and skip the Drive popup
  - `f28303ab` docs(review): PR #571 review (prior review; replaced by this file)
- Range reviewed: `0ba4fcd2..f28303ab` (base `main`; not a stacked PR). Behaviour reviewed against the feature
  commit `86253610`; the prior review markdown has no product logic.

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | SUCCESS |
| Documentation Build (Docusaurus) | SUCCESS |
| Backend Tests (Python) | SUCCESS |
| API Types (OpenAPI -> TypeScript) | SUCCESS |
| PR conventions (linked issue) | SUCCESS |
| Detect Docker-relevant changes | SUCCESS |
| Docker Build Test (Full Stack) | SKIPPED (not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The notebook still only prints "set"/"missing" for secrets via `colab_io.get_secret`. The
  diff adds no credentials, tokens, or `.env` content.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/src/` changes. The empty-string
  `export_date` default replaces a hard-coded date string; it is a form default, not served civic data.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. No `data/cache/` deletes, no large binaries, no warehouse writes.
  Notebook outputs are not committed. dbt/warehouse: not touched (no models in the diff).

## Strengths
- `owner_said_yes_to_this_run` still defaults to `False`, and bundle resolution sits after that gate
  (`AGENTS.md`, "GPU and paid compute"). No GPU/Colab run was started for this change.
- `latest_child` is store-agnostic (`Store.list_names`), so it works for Drive and the Databricks volume.
- A missing `policy_export/` becomes a clear `SystemExit` that names the store; a chosen bundle is printed.
- Explicit `export_date` is unchanged (`.strip() or latest_child(...)`).
- New Python stays in `packages/llm`; Conventional Commit + co-author trailer; issue #570 has the four parts and
  the PR says `Closes #570`.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`packages/llm/src/llm/gpu/colab_io.py:107-110`: `latest_child` matches only the first ten characters, so
   files and Drive duplicates can win.** `_RUN_DATE.match(n[:10])` accepts any name that *starts* with a date.
   `LocalStore.list_names` (and the Databricks list) returns files and folders alike. *Verified* in the worktree
   with a temp store: given `2026-11-17/` (with `videos.txt`) plus `2026-11-18.zip`, the helper returns
   `2026-11-18.zip`; with a Drive-style `2026-11-17 (1)/` it returns that folder. The notebook then builds
   `policy_export/<name>/videos.txt`. `colab_policy_analyze.main` reads the video list *before* loading a model
   (`:724-733`), so a bad pick exits with "no video ids" without spending GPU — but only after the owner has
   already ticked yes, and the error does not name the stray entry. Issue #570's contract says
   `YYYY-MM-DD...` (suffixes allowed), and the new test locks in `2026-11-17-pilot` over `2026-11-17`, so a
   bare `_RUN_DATE.match(n)` would fight the written contract. *Fix:* keep prefix/suffix flexibility, but only
   keep names for which `store.read_text(f"{rel_dir}/{n}/videos.txt")` is not `None` (or otherwise confirm a
   directory with a bundle). Add cases for a dated `.zip` and a `YYYY-MM-DD (1)` name.

2. **`web_docs/docs/deployment/colab-gemma-policy-analysis.md:70-86`: the runbook still describes the old
   notebook.** Step 5 says "Set `export_date`"; step 3 / the Drive bullet say Drive is mounted whenever Databricks
   secrets are missing. Blank-date → newest and the mount skip when `…/policy_export` already exists are the new
   common path. *Verified:* `rg export_date` / mount wording in that doc shows only the old text. *Fix:* document
   blank = newest dated folder (printed), and that cell 3 skips `drive.mount` when the bundle folder is already
   present.

### 🔵 Nits / suggestions (Minor)
3. **Notebook cell 3: the skip only applies when `<DRIVE_ROOT>/policy_export` already exists.** On a fresh
   runtime with Drive unmounted, `drive.mount` still runs and can still hit the blocked popup. The PR body's
   "no longer hits the blocked popup" is true for a re-run (or when the folder was copied onto the runtime), not
   the first Drive-backed open. Unverified on a live Colab session (no GPU/runtime used). Narrow the claim or
   point at Databricks secrets as the popup-free path.

4. **`colab_io.py:108`: docstring says names "start `YYYY-MM-DD`"**, which matches today's loose filter; after
   finding 1, say that only bundle folders (with `videos.txt`) count. The `"Store"` quotes are fine with
   `from __future__ import annotations`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/570-colab-notebook-defaults`; `Closes #570`; issue has Problem, Done when, Contract, Read first |
| Conventional Commits | Yes | `feat(llm): …` with co-author trailer |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | Helper in `packages/llm`; nothing new under `scripts/` |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | Folder date strings, not warehouse year columns |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | Partial | Runbook not updated (finding 2) |
| Telemetry and logging | n/a | No FastAPI change; notebook still uses `print` for operator status |
| Tests | Partial | Helper covered; notebook cells not executable in CI (see Test Coverage) |
| Shared libraries | Yes | Full `packages/llm` suite; `colab_io` dependents are only `colab_policy_*` inside the same package |
| GPU and paid compute | Yes | Gate default unchanged; lookup after gate; no GPU run started for the review |

## Test Coverage
- **Run locally** (worktree forced via `PYTHONPATH=…/packages/*/src:…`):
  - `pytest packages/llm/tests` → **230 passed**
  - `pytest …::test_latest_child_picks_the_newest_dated_folder` fails with `AttributeError` when
    `colab_io.py` is reverted to `main`, and passes again after restore
  - `ruff check` on the two changed Python files: clean
  - Frontend `tsc` / dbt: not applicable (no `web_app/` or `dbt_project/` changes)
- **PR body claims:** blank-date and mount-skip behaviour match the notebook source. The claim that local
  `pytest` cannot collect (dangling `open-navigator-backups` symlink) was **not** reproduced in this clean
  worktree; CI Backend Tests also passed. Notebook cells and the popup skip were **not** run on a Colab/GPU
  runtime (correct per AGENTS.md); those behaviours are code-traced only.
- **Covered:** newest dated name, ignore undated `notes.txt`, `None` for a missing dir.
- **Not covered:** dated files, Drive duplicate folder names, notebook integration.

## Verdict
**approve-with-nits.** Safe to merge as-is. Prefer tightening `latest_child` to real bundles (finding 1) and
updating the runbook (finding 2) in this PR or a short follow-up; the nits can ride along.
