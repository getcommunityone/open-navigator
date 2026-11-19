---
pr: 571
branch: feat/570-colab-notebook-defaults
title: "feat(llm): default the Colab policy notebook's bundle date and skip the Drive popup"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(llm): default the Colab policy notebook's bundle date and skip the Drive popup

## Summary
The PR makes two small changes to `notebooks/colab_gemma_policy_analysis.ipynb`. A blank `export_date` now resolves to
the newest dated folder under `policy_export/` through a new pure helper, `colab_io.latest_child`, and cell 3 skips
`drive.mount` when the bundle folder is already on the runtime. The change is small and works for the normal case, and
the GPU gate is untouched (`owner_said_yes_to_this_run` stays `False`, and the new lookup runs after it). The helper's
filter is looser than the bundle format the exporter writes: a stray file or a Drive duplicate folder can win "newest"
and send a run at a bundle that doesn't exist. That's a should-fix, but it fails with a clear error and nothing is
spent. The docs page also still describes the old behaviour. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 3 (+29 / -4, no generated files)
- Areas touched: packages (llm), notebooks
- Commits:
  - `86253610` feat(llm): default the Colab policy notebook's bundle date and skip the Drive popup
- Range reviewed: `0ba4fcd2..86253610` (base `main`; not a stacked PR)

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
- **Secrets:** clean. The notebook reads `HF_TOKEN` and the Databricks values through `colab_io.get_secret`, and only
  prints "set"/"missing". The diff adds no credentials.
- **Fabricated data in a served path:** clean. Nothing in `api/` or `web_app/`. The only constant is the empty-string
  default for `export_date`; it replaces a hard-coded date.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. No deletions, no data files. The notebook has no committed outputs.

## Strengths
- The paid-compute rule is kept: `owner_said_yes_to_this_run` still defaults to `False`, and the bundle lookup sits
  after the gate, so a blank date can't start a run on its own (`AGENTS.md`, "GPU and paid compute").
- `latest_child` is a pure function over the existing `Store` protocol, so it works on both `LocalStore` and
  `DatabricksVolumeStore`. It returns `None` for a missing folder, and the notebook turns that into a clear
  `SystemExit` that names the store.
- The notebook prints `bundle: <date>`, so the folder that was picked is visible.
- An explicit `export_date` still behaves as before (`.strip() or latest_child(...)`).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`packages/llm/src/llm/gpu/colab_io.py:109`: "newest" is matched on a 10-character name prefix, so files and
   duplicate folders can win.** `_RUN_DATE.match(n[:10])` accepts any name that merely starts with a date, and
   `list_names` returns files as well as folders (`LocalStore` uses `iterdir()`, and the Databricks store returns every
   entry). The exporter only writes exact `YYYY-MM-DD` folders (`colab_policy_export.py:373`, `check_run_date` anchors
   with `$`). *Verified:* in a temp store with `policy_export/2026-11-17/videos.txt`, adding a file
   `2026-11-18.zip` makes `latest_child` return `2026-11-18.zip`, and a Drive-style duplicate folder
   `2026-11-17 (1)` also beats `2026-11-17`. The notebook then points `--videos-file` at
   `policy_export/2026-11-18.zip/videos.txt`, which doesn't exist, and `colab_policy_analyze` stops with "no video ids"
   (`:732`). It stops cleanly, but only after the owner's yes and after the model setup, and the user has to find the
   stray name. The new test also locks in the loose rule: it expects `2026-11-17-pilot` to beat `2026-11-17`, a name the
   exporter never produces. *Fix:* match the full name with `_RUN_DATE.match(n)`, so only `YYYY-MM-DD` counts. Better
   still, prefer names whose `{n}/videos.txt` exists via `store.read_text`. Change the test to expect `2026-11-17`
   and add a case with a stray `2026-11-18.zip` file.
2. **`web_docs/docs/deployment/colab-gemma-policy-analysis.md:66-86`: the runbook still describes the old notebook.**
   Step 5 says "Set `export_date`", and step 3 and the Drive bullet say Drive is mounted whenever there are no
   Databricks secrets. Both are now wrong in the common case (blank means newest; the mount is skipped when the bundle
   folder exists). Per `AGENTS.md` ("Decisions are written down"), the doc should state the blank-date rule and the
   skip condition. *Verified:* `rg export_date` over the doc shows only the old wording.

### 🔵 Nits / suggestions (Minor)
3. **Notebook cell 3: the skip only helps when `<DRIVE_ROOT>/policy_export` already exists.** On a fresh runtime
   with Drive unmounted that folder isn't there, so `drive.mount` still opens the popup. The PR body says Cursor's
   browser "no longer hits the blocked popup". That holds for a re-run on the same runtime, not for the first run.
   I couldn't test it, because it needs a Colab runtime. Word the PR and doc claim narrowly ("when the bundle is
   already on the runtime"), or add a Databricks-secrets note as the popup-free path.
4. **`colab_io.py:107`: the docstring says "names start `YYYY-MM-DD`, so the last in sort order".** After fix 1 it
   should say "names are exactly `YYYY-MM-DD`". The `"Store"` annotation doesn't need quotes: the module has
   `from __future__ import annotations` (line 13).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/570-colab-notebook-defaults`; body says `Closes #570`; issue #570 has Problem, Done when, Contract, Read first |
| Conventional Commits | Yes | `feat(llm): ...` with the co-author trailer |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | Helper added to `packages/llm`; nothing in `scripts/` |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | The date is a folder name string, not a year column |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | Partial | Runbook not updated (finding 2) |
| Telemetry and logging | n/a | No FastAPI work; the notebook uses `print` for user-facing status, as before |
| Tests | Partial | The helper is tested; the notebook cell changes can't be (see Test Coverage) |
| Shared libraries | Yes | Full `packages/llm` suite run; the only dependents of `colab_io` are `colab_policy_export` and `colab_policy_analyze`, both inside it |
| GPU and paid compute | Yes | Gate default unchanged; the lookup runs after it; no GPU run started |

## Test Coverage
- **Run locally** (worktree code forced through `PYTHONPATH`): `pytest packages/llm/tests` gives 230 passed, including
  the 26 in `test_colab_policy_analyze.py`. `ruff check` on the two changed Python files is clean. The notebook is valid
  JSON. This shows the PR's "pytest cannot collect from this machine" caveat is specific to the author's checkout; the
  suite runs fine from a clean worktree, and CI Backend Tests passed.
- **Covered:** `latest_child` picks the last dated name, ignores a non-dated file, and returns `None` for a missing
  folder. It fails without the helper (`AttributeError`). The test is thin: it doesn't cover a dated file or a
  duplicate-folder name (finding 1).
- **Not covered / unverified:** the notebook cells. The blank-date resolution and the mount skip ran only by reading
  the code. The PR body says as much. No GPU run was started, correctly.

## Verdict
**approve-with-nits.** Nothing blocks the merge. Before or soon after it, tighten `latest_child` to exact
`YYYY-MM-DD` names (finding 1) and update the runbook (finding 2). The rest are wording.
