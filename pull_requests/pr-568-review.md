---
pr: 568
branch: feat/566-erd-row-counts
title: "feat(erd): show live row counts and subject-area totals on the marts ERD"
author: jcbowyer
reviewed_at: 2026-11-19
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(erd): show live row counts and subject-area totals on the marts ERD

## Summary
The branch adds `--dsn` / `--schema` to `python -m erd`. New `erd.stats.table_stats` runs an exact
`count(*)` per mart and reads whether Postgres holds a primary key; table headers show `N rows`, subject-area
titles show table count / row total / PK count, and the legend names the schema and measurement minute. Gaps
stay gaps ("rows not measured yet"; area totals omit unmeasured tables and say so). I reproduced the PR body's
warehouse claims on `localhost:5433/open_navigator` (108 marts, 96 measured, 2 views, 10 absent; Jurisdictions
exact total 580,674; Browse 104,275; Topics 14,119; `public` 11/11 PK + 74 views; 16 `gold` tables without a PK).
The six package tests pass and required CI is green. Nothing fabricated is served. Remaining gaps: no test of
`table_stats` / `--dsn`, a stale `uv.lock` for the new `db` extra, and a quiet break of the issue Contract that
promised an unchanged diagram when `--dsn` is omitted. Approve with nits.

## Scope of Change
- Files changed: 8 (+123 / -13 excluding the two regenerated `.drawio` files; those are one long line each)
- Areas touched: packages (`erd`) / web_docs (`marts-erd.md`, two regenerated `.drawio` diagrams)
- Commits:
  - `2e46c972` feat(erd): show live row counts and subject-area totals on the marts ERD (#566)
  - `960e50db` docs(erd): regenerate the marts ERD with live row counts and subject-area totals (#566)
  - `220e42b1` docs(review): PR #568 review (prior review; this file supersedes it)
- Range reviewed: `0ba4fcd2..220e42b1` (base is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Docker Build Test (Full Stack) | skipped (not required; no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Docs example DSN `postgresql://postgres:password@localhost:5433/open_navigator` is the repo's
  local-warehouse default (same string elsewhere under `web_docs/docs`), not a real credential. No tokens or
  `.env` content in the diff.
- **Fabricated data in a served path:** clean. `packages/erd` is an offline diagram generator, not `api/` /
  `web_app/src`. Counts come from `count(*)`. Absent or view marts stay "rows not measured yet"; an area with no
  measured table shows no row total (`area_summary` → `None`). Verified Jurisdictions / Browse / Topics exact
  totals match the committed diagram and the PR body.
- **Personal data:** clean. Only table names, row counts and PK flags are read.
- **Destructive or bulky data changes:** clean. Queries are `SELECT` only. The two `.drawio` files are already
  tracked and regenerated in place (entity ~182 KB → 257 KB, full ~1.04 MB → 1.38 MB, from more marts plus
  headers). PNGs remain LFS pointers and are untouched. Nothing touches `data/cache/`.

## Strengths
- Honest empty states: unmeasured tables, partial area totals ("in 11 measured"), and all-unmeasured Elections
  (no row line) each render as a gap; a unit test asserts it.
- `table_stats` skips views and partition children and only returns tables that exist. Read-only call:
  `event_place_geocoded` (view) and `dim_fake` omitted; `jurisdictions` → `pk: True`,
  `jurisdiction_state_aggregate` → `pk: False`, matching `pg_constraint`.
- `psycopg2` is an optional `db` extra with a clear `SystemExit` when missing, so the default install and docs
  build stay free of it.
- Identifiers go through `psycopg2.sql.Identifier`; the table list is a bound parameter.
- Measured PK comes from Postgres, so declared-but-missing keys surface; that discovery is tracked in #567.
- Legend names schema and UTC minute, so a stale diagram is recognisable.
- Docs updated in the same PR; loguru on the measured/modelled counts.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`packages/erd/src/erd/stats.py` and `__main__.py:37-42`: the new database path has no test.** The two new
   tests cover `area_summary` and rendering with hand-built `stats`. Nothing exercises `table_stats` (relkind
   filter, `NOT relispartition`, PK `EXISTS`, skipping absent/views), `measured_note`, or the `--dsn` branch of
   `main`. *Verified:* `rg` finds those names only in `stats.py` / `__main__.py`, not under `packages/erd/tests`.
   Reverting `dictionary.py` to base makes the new tests fail at import (`area_summary` missing), so rendering is
   guarded; `stats.py` is not. Behaviour was checked by hand against the warehouse (above). *Fix:* fake
   `psycopg2.connect` (catalog rows + `count(*)` returns), assert the dict; test `measured_note` with a fixed
   `when`; monkeypatch `table_stats` in `main(["--dsn", ...])` and assert `STATS_NOTE` reaches the legend.

2. **`packages/erd/pyproject.toml` optional `db` extra leaves `uv.lock` stale.** *Verified:* `uv lock --check`
   fails on HEAD ("The lockfile at `uv.lock` needs to be updated"); the `communityone-erd` block still lists only
   loguru / numpy / pyyaml and has no `psycopg2-binary` optional metadata. CI is green (does not use `--locked`),
   but `uv sync --locked` / `uv lock --check` fail. *Fix:* run `uv lock` and commit.

3. **Issue Contract says "With no `--dsn` the output is unchanged", but area titles always change.**
   `dictionary.py:432` always calls `area_title(...)` (after `stats = stats or {}`), so even without a DSN every
   subject-area box gains "N tables · K of N with a primary key" from dbt declarations. *Verified:* `build(model)`
   with `stats=None` embeds those subtitles; base `marts_entity.drawio` had plain `Jurisdictions`, HEAD has the
   measured subtitle. Headers without counts still say "rows not measured yet" (good). The docs soften this
   ("Leave out `--dsn` … no counts") but the issue Contract does not. *Fix:* either gate the subtitle on
   `STATS_NOTE` / a non-empty measured `stats`, or add a dated Contract line on #566 that area titles always show
   table/PK counts from declarations when unmeasured.

### 🔵 Nits / suggestions (Minor)
4. **`area_summary` / `area_title`: "N of M with a primary key" mixes Postgres and dbt.** Measured tables use
   `pg_constraint`; unmeasured ones use the declaration. Elections reads "0 of 5" though none are built here;
   Topics reads "8 of 8" with only 7 measured. Docs explain it; the title does not. Prefer counting PK over
   measured tables only (as rows do), or mark the declared part.

5. **`stats.py:21-36`: connection is not read-only, has no statement timeout, and is not closed.**
   `with psycopg2.connect(...) as conn` ends the transaction but leaves the connection open (`closed == 0` after
   the `with`). The tool `count(*)`s every mart, including multi‑GB tables. *Fix:* `set_session(readonly=True)`,
   `contextlib.closing`, and consider a statement timeout.

6. **Counts are not one snapshot.** Each table is a separate `count(*)`; the legend shows one minute. Fine for a
   diagram; docs could say "about" or name the start time.

7. **Issue Contract names `erd.stats.row_counts`; the code ships `table_stats` and also returns `pk`.** Per
   `AGENTS.md`, add a dated Contract line rather than rewriting the original. The Chromium render claim in the PR
   test plan was not reproduced here (unverified); XML was checked instead (104 "N rows" labels, 12 "rows not
   measured yet", nine area titles, one legend line).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/566-erd-row-counts`; body `Closes #566` / `Refs #567`. #566 and #567 have Problem, Done when, Contract, Read first; #567 is the `action-item` for the 16 PK-less tables. PR conventions check passes |
| Conventional Commits | Yes | `feat(erd): …` and `docs(erd): …`, both with co-author trailer |
| No fabricated data | Yes | Scan above; measured totals match exact `count(*)` where checked |
| New Python in `packages/` | Yes | `packages/erd/src/erd/stats.py`; entry point stays `python -m erd`; nothing in `scripts/` |
| dbt for transformations | n/a | Catalog/count for a diagram only; no warehouse transform in Python |
| Naming | n/a | No models/columns added |
| Keys | n/a | No `public` model changed; gap reported via #567 |
| Calendar years | n/a | None |
| Scope label matches filter | n/a | No `web_app` change |
| Match evidence on filtered tiles | n/a | No `web_app` change |
| Docs | Yes | `web_docs/docs/data-sources/marts-erd.md`; no new root `.md` |
| Telemetry and logging | Yes | loguru for measured vs modelled counts |
| Tests | Partial | `area_summary` + rendering covered; `table_stats` / `--dsn` not (finding 1); no-dsn contract untested (finding 3) |
| Shared libraries | Yes | `packages/erd` tests run; no other package imports `erd` for runtime; `uv.lock` stale (finding 2) |

## Test Coverage
- **Run locally** (worktree code forced with `PYTHONPATH` over the main `.venv`):
  - `pytest packages/erd/tests`: 6 passed.
  - `ruff check packages/erd`: clean.
  - `uv lock --check`: fails on HEAD (finding 2).
  - Reverting `dictionary.py` to base → import error on the new tests; restored afterwards; 6 passed again.
- **Warehouse (read-only, `localhost:5433/open_navigator`, `default_transaction_read_only` / `set_session(readonly=True)`):**
  - 108 modelled marts; 96 tables in `gold`; views `event_place_geocoded`, `event_youtube_with_jurisdiction`; 10
    absent (5 elections dims/facts, `dim_jurisdictions_master`, `llm_usage_daily`, `ordinance*`, `tag_organization`).
  - Exact area totals: Jurisdictions 580,674; Browse and reports 104,275; Topics and tags 14,119 — match the
    diagram and PR body. Large areas (Bills, MDM, Nonprofits, Events) were not re-`count(*)`'d end-to-end (multi‑GB);
    their diagram titles match the PR body and the committed XML.
  - `public`: 11 tables all with PK, 74 views. `gold`: 16 tables without PK.
- **Not run:** full 25-minute generator; headless Chromium / draw.io open (PR's unchecked reviewer item). No
  frontend/API/dbt model changes, so `tsc` and dbt compile were not required.
- **Not covered by tests:** findings 1 and 3.

## Verdict
**approve-with-nits.** Correctness of the measured diagram is solid and CI is green. Before merge, please add
tests for `table_stats` / `measured_note` / `--dsn` (finding 1), refresh `uv.lock` (finding 2), and either gate
area titles when there is no DSN or date-amend the Contract on #566 (finding 3). Nits 4–7 can land as one
`action-item` issue.
