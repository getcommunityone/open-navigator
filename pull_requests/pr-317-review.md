---
pr: 317
branch: fix/313-fec-workers-auto
title: "fix(scrapers): let the FEC unzipper pick its worker count and run as a module"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(scrapers): let the FEC unzipper pick its worker count and run as a module

## Summary

There were two bugs in `unzip_fec_data`:
- `--workers 0` called a `cpu_count` that was never imported (`NameError`);
- `main()` imported `fec_paths` as a top-level module, so `python -m scrapers.fec.unzip_fec_data` couldn't run.

The PR imports `cpu_count` from `multiprocessing`, and imports `fec_paths` through the package with a fallback to
the script form. New tests run `main()` against a temp `--base-dir`, so nothing under `data/cache/` is touched.
Closes #313. Approve.

## Scope of Change

- Files changed: 2 (`unzip_fec_data.py`, new `packages/scrapers/tests/test_fec_unzip_workers.py`)
- Areas touched: packages (scrapers)
- Commits: ef533cde fix(scrapers): let the FEC unzipper pick its worker count and run as a module

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none.
- Personal data: none.
- Destructive changes: none. The tests and the manual runs used temp folders only, and `data/cache/` was never
  touched.

## Findings

None blocking, none to fix, no nits. Verified:
- Before the fix, the tests failed (`ModuleNotFoundError: fec_paths`), and the script run failed with
  `NameError: cpu_count`.
- After the fix, both pass.
- Run both ways, the tool logs "Auto-detected 3 workers".
- `ruff check --select F821` is clean.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #313 has Problem, Done when, Contract and Read first; `Closes #313` |
| Conventional Commits | Yes | `fix(scrapers): ...` with the co-author trailer |
| New Python in `packages/` | Yes | The change makes the package CLI form (`python -m`) work, as `CLAUDE.md` asks |
| Tests | Yes | The regression tests fail before the change and pass after |
| Shared libraries | Yes | `packages/scrapers/tests` has 2 collection errors (`aiolimiter` missing), the same on `main` (#305) |

## Verdict

Approve once the required checks are green.
