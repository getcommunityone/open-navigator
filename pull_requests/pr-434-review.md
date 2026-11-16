---
pr: 434
branch: fix/423-jurisdiction-count-claims
title: "fix(api,web_app,docs): stop serving and claiming made-up jurisdiction counts"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (Claude Code session; no reviewer subagent, as the rubric allows)
verdict: approve-with-nits
---

# PR Review: fix(api,web_app,docs): stop serving and claiming made-up jurisdiction counts

## Summary
`/data/status` (`api/main.py`) and `/api/data/status` (`api/app.py`) returned typed-in numbers: 90,000
jurisdictions, 13,000 school districts, 3,000,000 nonprofits and MeetingBank 1,366. They now read the national
`jurisdiction_state_aggregate` row that `/api/stats` serves, plus a county and city count from `civic_jurisdiction`.
Each value is `null` when it can't be computed, and the response shapes are unchanged. The web app no longer claims
"90,000+": the Analytics card shows the live `governments` count, or "—". The docs now cite the Census of Governments
with a source wherever they mean the national total. The fix removes a real "No Fabricated Data" violation and is
tested. The only findings are a commit without a scope and an unlinked follow-up. The verdict is approve-with-nits.

## Scope of Change
- Files changed: 33 (+433 / -143)
- Areas touched: api, web_app, web_docs, packages (one doc), `.huggingface`, `.github`
- Commits:
  - 995a2e74 fix(api): serve real counts or null from the data status routes, never constants
  - 8b35860a fix(web_app): stop claiming 90,000+ jurisdictions; show the live government count
  - b49bd91a docs: describe the national government count correctly, and don't claim it as coverage
- Range reviewed: `fb865cc2..b49bd91a`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Docker Build Test (Full Stack) | pass |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean, and better than before. The PR removes the hard-coded counts from both
  status routes and from `Analytics.tsx`. The per-source meeting counts, which aren't modeled, are now `null` or
  "unavailable", not guesses. The new `fetch_national_reference_counts` returns `None` for any missing row, column or
  DB error, and doesn't cache an error. Other hard-coded stats remain elsewhere ("1.8M nonprofits", the Analytics
  budget card, nav chips); they are out of scope and tracked in #444.
- Personal data: clean.
- Destructive or bulky data changes: clean (read-only queries).

## Strengths
- I checked the Census figures in the docs against the sources. The 2022 Census of Governments breakdown (3,031 /
  19,491 / 16,214 / 12,546 / 39,555 = 90,837) is correct, and the Census Bureau's Government Organization Summary
  2022-2025 page gives 91,438 for 2025. The "~51,000 excluding special districts" in `jurisdiction-setup.md` matches
  90,837 − 39,555 = 51,282.
- Both new DB calls are wrapped in OpenTelemetry spans (`data_status.national_aggregate`,
  `data_status.civic_jurisdiction_counts`), as `CLAUDE.md` asks for FastAPI work.
- `public.civic_jurisdiction` exists in the local warehouse and has `county` and `city` classifications, so the
  grouped count will return real numbers.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- Commit b49bd91a's subject is `docs: ...` with no scope. `CLAUDE.md` asks for `<type>(<scope>): <description>`, for
  example `docs(web_docs): ...`. Not rewritten, since the branch has an open PR (no force-push); the squash-merge
  title (`fix(api,web_app,docs): ...`) is compliant.
- The PR description lists the remaining hard-coded stats as a "follow-up issue" without a number. The issue exists
  (#444); link it from the PR, as `AGENTS.md` asks.
- `api/routes/stats_neon.py` (`fetch_national_reference_counts`): if `civic_jurisdiction` exists but has no `county`
  rows, `counties` is `0`, not `None`. That is a true count of the table, so it is acceptable, but an empty serving
  table would read as "zero counties" and not as "unavailable".

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/423-...`; `Closes #423`; #423 has all four parts; follow-up #444 exists but isn't linked |
| Conventional Commits | Partial | b49bd91a has no scope (nit) |
| No fabricated data | Yes | Removes fabricated counts; missing data is `null` / "—" |
| New Python in `packages/` | Yes | `scripts/` mentions are left for the port, as the PR says |
| dbt for transformations | Yes | Reads existing serving tables; no SQL transformation in Python |
| Naming | N/A | |
| Keys | N/A | No model changes |
| Calendar years | N/A | |
| Scope label matches filter | N/A | The Analytics card is national only and unscoped |
| Match evidence on filtered tiles | N/A | |
| Docs | Yes | Edits in `web_docs/docs/`; no new root `.md` |
| Telemetry and logging | Yes | OTel spans on both queries |
| Tests | Yes | `tests/test_api_data_status.py` (5 tests: real values, null on missing, no error cached, both routes) |
| Shared libraries | N/A | No `packages/` code changed |

## Test Coverage
Ran locally: `pytest tests/test_api_data_status.py` (5 passed) and `pytest tests -k "status or stats or main"`
(24 passed). `ruff check` adds no errors (`app.py` 9 before and after, `main.py` 54 → 53, `stats_neon.py` 0; the new
test file is clean). The frontend `tsc` and `vite build` and the Docusaurus build pass in CI on the head commit. A
grep for "90,000+", "90K+" and "90k+" in `web_app/src`, `api`, `web_docs/docs` and `web_docs/src` finds only a
"before" code sample in `development/real-time-statistics.md`, which is fine.

## Verdict
approve-with-nits. Nothing has to change before merge. Link #444 in the PR description.
