---
pr: 577
branch: chore/466-declare-requests
title: "chore(deps): declare requests and list the files that still use it"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: chore(deps): declare requests and list the files that still use it

## Summary
The PR declares `requests>=2.31` in `requirements.txt` and in the three workspace packages that import it
(`ingestion`, `llm`, `scrapers`). It updates `uv.lock` to match, and adds an "HTTP clients" item to the cleanup roadmap
that points new HTTP code at `core_lib.http` and lists the files that still import `requests`. It changes no
behaviour. I could reproduce the PR's claims: the list of 27 files matches a search of `packages/` exactly, no session
mounts a retry adapter, `uv lock --check` is clean, and the three packages' test suites pass. Only nits remain, so the
verdict is approve-with-nits.

## Scope of Change
- Files changed: 6 (+16 / -0; `uv.lock` is +6 of that)
- Areas touched: packages (dependency declarations), web_docs, dependency lock
- Commits: `5c5e5fc1` chore(deps): declare requests and list the files that still use it
- Range reviewed: `0ba4fcd2..5c5e5fc1` (merge base with `main`; the PR's base is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | success (not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. A search of the diff for key, password, token, secret and credentialed-URL patterns found nothing.
- **Fabricated data in a served path:** clean. There are no changes under `api/` or `web_app/src/`.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. There are no deletions, and the largest file is +6 lines in `uv.lock`.

## Strengths
- The change is minimal and does what issue #466 asks. The lock diff is only the four `requests` declarations (two
  `dependencies` entries and two `requires-dist` entries), and `uv lock --check` reports it consistent.
- The PR body says plainly that it found 27 files where the issue says 29, and offers to add the other two.
- The roadmap note records why: no session mounts a retry adapter, unlike `core_lib.http`.
- Each package's declaration is next to the code that imports it. Not every importing package already depended on
  `requests` indirectly, so this is the right level.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. `requirements.txt:13`: the comment hard-codes "27 package files". The number will drift as scrapers move to
   `core_lib.http`, and the roadmap already holds the list. Verified by reading the line against the roadmap. Fix: drop
   the count, e.g. `# legacy HTTP in packages (see cleanup-roadmap, HTTP clients)`.
2. `cleanup-roadmap.md` (new "HTTP clients" item): the file paths omit the `packages/<pkg>/src/` prefix
   (`ingestion/census/counties.py` is really `packages/ingestion/src/ingestion/census/counties.py`). I compared the list
   against `rg -l '^\s*(import requests|from requests)' packages`, and it matches once the prefix is stripped. Fix: say
   "module paths" in the sentence, or use full paths so they can be found by grep.
3. The 27-vs-29 gap in the issue's count is still open. I found no other import form in `packages/`: no
   `import requests as`, no `importlib` and no `__import__`. Only `scripts/` or `api/` could account for the extra two.
   Say where the 29 came from, or correct the issue text, so "Done when" matches what shipped. The PR body's offer to
   add the other two files is a reasonable resolution.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `chore/466-declare-requests`; body says `Closes #466`; the issue has Problem, Done when, Contract and Read first; PR conventions check passes |
| Conventional Commits | Yes | `chore(deps): ...` with a Cursor co-author trailer |
| No fabricated data | Yes | Not applicable; no served code changed |
| New Python in `packages/` | Yes | No Python added |
| dbt for transformations | Yes | Not applicable |
| Naming | Yes | Not applicable |
| Keys | Yes | Not applicable |
| Calendar years | Yes | Not applicable |
| Scope label matches filter | Yes | Not applicable |
| Match evidence on filtered tiles | Yes | Not applicable |
| Docs | Yes | Edit is in an existing page under `web_docs/docs/development/`; the Documentation Build passes |
| Telemetry and logging | Yes | Not applicable |
| Tests | Yes | Dependency declarations only; no behaviour to test. CI and the local run cover import health |
| Shared libraries | Yes | Packages' tests run for all three touched packages (see below) |

## Test Coverage
No behaviour changed, so no new test is expected. I ran these locally in a worktree, with the worktree's package code
forced onto `PYTHONPATH`:
- `pytest packages/ingestion/tests packages/llm/tests packages/scrapers/tests`: all passed, with one skipped.
- `uv lock --check`: resolved 212 packages with no changes needed.
- All `pyproject.toml` files parse (`tomllib`), and `requests` 2.33.1 is installed in the main venv.
- Searches of `packages/` confirmed the file list (27 files: ingestion 5, llm 1, scrapers 21) and that no
  `HTTPAdapter` or `Retry` is used anywhere.
- Not run: `ruff`, `tsc` and dbt, because no Python source, frontend or dbt file changed.

## Verdict
approve-with-nits. Nothing blocks the merge. Consider dropping the hard-coded count from the `requirements.txt` comment
and clarifying the roadmap paths and the 29-vs-27 count.
