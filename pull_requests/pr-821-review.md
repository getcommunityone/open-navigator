---
pr: 821
branch: fix/820-loader-renamed-meta
title: "fix(llm): load analyses whose files were renamed after the run"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve
---

# PR Review: fix(llm): load analyses whose files were renamed after the run

## Summary
The cache loader skipped any analysis whose metadata recorded a different file name. That rule was written for one
case (a light file beside a full run's metadata) but also caught analyses renamed after a date or title correction:
49 in the owner's run. The PR compares the tier instead of the name. It is a one-line rule change with a regression
test built from the real file names. Approve.

## Scope of Change
- Files changed: 4 (excluding this review)
- Areas touched: packages (llm) / tests / web_docs
- Commits: `da8feed7` fix(llm): load analyses whose files were renamed after the run
- Range reviewed: `origin/main...origin/fix/820-loader-renamed-meta`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. The change loads more real analyses; it writes nothing to `data/cache/`.

## Strengths
- The evidence is first-hand: the owner's loader log and the recorded `analysis_json` path for one affected meeting.
- The #796 protection is kept and tested in both directions.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The rule now trusts that a metadata file beside an analysis of the same tier is that analysis's record. Traced:
  `load_meta` already pairs by file stem, and the loader separately compares the metadata's own `analysis_tier` with
  the file's tier, so a same-tier, same-stem pairing was the only link there ever was.
- One affected meeting was inspected, not all 49. Others could be genuine tier mismatches; those still skip.
- The stale path inside renamed metadata is left as is.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #820 with the four parts; branch `fix/820-loader-renamed-meta`; `Closes #820`; follow-up #822 |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | |
| Docs | Yes | `web_docs/docs/development/batch-load-tab.md` |
| Tests | Yes | The new test fails on `main` |
| Shared libraries | Yes | `tests/test_loader_gate_796.py` run; CI runs the rest |

## Test Coverage
`pytest tests/test_loader_gate_796.py`: 28 passed. Not run: the loader against the real cache (no access from the
session that wrote this).

## Verdict
approve. After merge, re-run the loader with `--dry-run` and confirm the warnings fall.
