---
pr: 589
branch: chore/462-remove-stealth
title: "chore(scripts): archive the stealth-using eboard debug scripts and drop enable_stealth"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: chore(scripts): archive the stealth-using eboard debug scripts and drop enable_stealth

## Summary
The PR finishes the stealth removal from #443 for the three legacy `scripts/` files named in #462. It moves
`debug_eboard.py` and `try_scrape_with_cookies.py` to `archive/datasources/eboard/` with `git mv` (similarity 100%),
removes `enable_stealth=True` from `contact_extract_crawl4ai.py`, rewrites `scripts/eboard/README.md`, and adds a guard
test that fails if any `scripts/**/*.py` imports `playwright_stealth` or sets `enable_stealth=True`. I reproduced the
claims: the test passes on the head and fails when either the old crawl4ai line or an un-archived stealth script is put
back, nothing imports the archived scripts, and no `playwright_stealth` or `enable_stealth` is left in `*.py` outside
`archive/` and the guard test. CI is green. The only finding is that the guard is a narrow pattern match. Approve with
that nit.

## Scope of Change
- Files changed: 5 (+20 / -18; the two renames are 0-line changes)
- Areas touched: scripts (legacy, shrinking), archive, packages (scrapers test)
- Commits:
  - `47918f23` chore(scripts): archive the stealth-using eboard debug scripts and drop enable_stealth
- Range reviewed: `0ba4fcd2..47918f23` (merge base with `main`; the PR base is `main`, not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required; no Docker files change) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The diff holds no keys, tokens, cookies or credentialed URLs. The archived scripts moved
  byte-for-byte (100% rename), so their content is unchanged.
- **Fabricated data in a served path:** clean. Nothing in `api/` or `web_app/src/`.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. Two small scripts are renamed, not deleted. `data/cache/` is untouched,
  and no raw data, log or dump is added.

## Strengths
- Archiving rather than porting is justified, and I could confirm it: `rg "debug_eboard|try_scrape_with_cookies"`
  finds nothing but the scripts' own usage strings and the new README line. No test, docs page or pipeline imports
  them.
- `git mv` keeps history, and `scripts/` shrinks instead of growing, as `CLAUDE.md` asks.
- The PR is honest about scope. It leaves `magic=True` alone and logs it as #588 (open, labelled `action-item`), and it
  says the live GA contact-roster test was not run.
- A side effect worth knowing: the main venv's crawl4ai (0.4.24) does not accept `enable_stealth` at all.
  `BrowserConfig(headless=True, enable_stealth=True)` raises `TypeError` there, and the new
  `BrowserConfig(headless=True)` constructs fine. So on that version the old line was a crash, not just a policy
  violation. The PR body doesn't mention this.
- The guard test is a real regression test: it fails before the change, and it covers the files that still run.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **`packages/scrapers/tests/test_browser_block.py:78-88`: the guard is a literal pattern match, so it catches less
   than its docstring says.** The flag regex `\benable_stealth\s*=\s*True\b` misses `enable_stealth=flag`,
   `enable_stealth = bool(...)` and a dict-unpacked config, and `_STEALTH_IMPORT` matches only `from playwright_stealth`
   and `import playwright_stealth` at the start of a line (so an indented import inside a function or a `try:` block is
   still caught, but `__import__("playwright_stealth")` is not). It also scans only `scripts/`, so a stealth setting
   added under `tests/` or a root file passes. *Verified by reading the two patterns; the real offenders (the old
   crawl4ai line, an un-archived script) do trip it.* *Fix, optional:* match `enable_stealth\s*=\s*(?!False\b)` (any
   value other than a literal `False`) and say in the docstring that it is a tripwire, not a proof. This is not worth
   blocking the PR.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `chore/462-remove-stealth`; body says `Closes #462`; #462 has Problem, Done when, Contract, Read first; the follow-up found is its own issue (#588). The PR doesn't repeat #462's Attributes table (`Follow-up of #443`), which `AGENTS.md` asks for on planned work; the conventions check passes without it |
| Conventional Commits | Yes | `chore(scripts): …` with the co-author trailer |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | Nothing new in `scripts/`; the only addition is a test in `packages/scrapers/tests` |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | `scripts/eboard/README.md` is a README inside `scripts/`, not a new root `.md`. `export_chrome_cookies.py` is described accurately (its docstring says YouTube cookies from Chrome) |
| Telemetry and logging | n/a | |
| Tests | Yes | New test fails without the change (below) |
| Shared libraries | Yes | Only a test in `packages/scrapers` changed; its full test file was run. No source in `packages/` changed, so there are no dependents to re-run |

## Test Coverage
- **Run locally (worktree code, main venv, `PYTHONPATH` forced to the worktree):**
  - `packages/scrapers/tests/test_browser_block.py`: 22 passed.
  - With `contact_extract_crawl4ai.py` reverted to `main`'s version: the new test fails (1 failed, 21 passed).
    Restored with `git checkout`.
  - With `debug_eboard.py` moved back into `scripts/eboard/`: the new test fails (1 failed, 21 passed). Reset after.
  - `ruff check` on the test file and `contact_extract_crawl4ai.py`: clean. `py_compile` on the crawl4ai script:
    clean.
  - `rg "playwright_stealth|enable_stealth" --glob '*.py'`: only `archive/` and the guard test.
  - No frontend, API or dbt files changed, so `tsc` and `dbt ls` do not apply.
- **Not verified:** that crawl4ai extracts a real page with the plain `BrowserConfig`. The live GA contact-roster test
  (`tests/test_ga_contact_scraper_regression.py`) needs the network and an LLM key, and the PR says it wasn't run. I
  confirmed only that `BrowserConfig(headless=True)` constructs on crawl4ai 0.4.24. Behaviour on a newer crawl4ai
  (`requirements.txt` allows `>=0.4.0`) is unverified here. Three modules import the script (two discovery pipelines
  and a refresh script), so a first live run after merge is the real check.
- **Not covered by a test:** the archived scripts themselves (by design) and the guard's blind spots in nit 1.

## Verdict
**approve-with-nits.** Nothing blocks the merge. Nit 1 can be fixed in this PR or left. The PR's claims hold, apart from
the live-extraction one, which it already marks as unrun.
