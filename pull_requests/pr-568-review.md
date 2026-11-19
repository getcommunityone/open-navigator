---
pr: 568
branch: feat/566-erd-row-counts
title: "feat(erd): show live row counts and subject-area totals on the marts ERD"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(erd): show live row counts and subject-area totals on the marts ERD

## Summary
The branch adds `--dsn` and `--schema` to `python -m erd`. A new `erd.stats.table_stats` counts each mart with an
exact `count(*)` and reads whether Postgres holds a primary key on it. The ERD then shows `N rows` in each table
header and a table count, row total and PK count in each subject-area title. The legend says which schema was
counted and when. A mart that isn't built as a table says "rows not measured yet", never 0, and an area total
covers only measured tables and says so. I reproduced the PR body's claims about the warehouse (108 marts, 96
measured, 12 not, 10 absent and 2 views; `public` 11 tables with a PK and 74 views; 16 `gold` tables without a PK),
and the 6 package tests pass. Nothing is fabricated: every number comes from the database or is shown as a gap. The
one real gap is that the new query logic (`table_stats`, `--dsn` wiring) has no test. The rest are nits. Approve
with nits.

## Scope of Change
- Files changed: 8 (+125 / -15; the two regenerated `.drawio` files are one long line each and are generated output)
- Areas touched: packages (`erd`) / web_docs (`marts-erd.md`, two regenerated `.drawio` diagrams)
- Commits:
  - `2e46c972` feat(erd): show live row counts and subject-area totals on the marts ERD (#566)
  - `960e50db` docs(erd): regenerate the marts ERD with live row counts and subject-area totals (#566)
- Range reviewed: `0ba4fcd2..960e50db` (base is `main`, merge base `0ba4fcd2`)

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
- **Secrets:** clean. The docs command example uses `postgresql://postgres:password@localhost:5433/open_navigator`,
  the repo's local-warehouse default (the same string is in 6 other docs under `web_docs/docs`), not a real
  credential. The `.drawio` diffs contain no DSN; the "password/token" matches are column descriptions
  ("Prompt tokens…", "stemmed token").
- **Fabricated data in a served path:** clean. `packages/erd` is an offline generator, not `api/` or `web_app/src`.
  Counts come from `count(*)`; an absent or view mart gets "rows not measured yet"; an area with no measured table
  shows no row total at all (`area_summary` returns `None`), so a gap is never drawn as 0. I re-derived the area
  tables, measured counts and totals from `pg_class` and they match the diagram and the PR body.
- **Personal data:** clean. Only table names, row counts and PK flags are read.
- **Destructive or bulky data changes:** clean. The query is `SELECT` only. The two `.drawio` files are already
  tracked and are regenerated in place (entity 181 KB to 256 KB, full 1.04 MB to 1.38 MB, because the model now has
  108 marts instead of 85 plus the new headers). The PNGs are LFS pointers and are untouched.

## Strengths
- Honest empty states: unmeasured tables, partial area totals ("in 11 measured") and an all-unmeasured area
  (Elections) each render as a gap, and a test asserts it.
- `table_stats` skips views and partition children and only returns tables that exist. I ran it read-only: a view
  (`event_place_geocoded`) and a missing model (`dim_fake`) are omitted, and `jurisdiction_state_aggregate` is
  reported with `pk: False` and `jurisdictions` with `pk: True`, matching `pg_constraint`.
- `psycopg2` is an optional `db` extra, with a clear `SystemExit` message when it is missing, so the package's
  default install and the docs build are unaffected.
- Identifiers go through `psycopg2.sql.Identifier`, and the table list is a bound parameter.
- The PK shown for a measured table is Postgres's own, so a declared-but-missing key shows up. This surfaced the
  16 tables tracked in #567, which is a good use of the feature.
- The legend line names the schema and the minute of measurement, so a stale diagram is recognisable as stale.
- Docs updated in the same PR (`marts-erd.md`), including the regenerate command and how PKs are read.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`packages/erd/src/erd/stats.py:13-39` and `__main__.py:37-43`: the new database logic has no test.** The 2 new
   tests cover `area_summary` and the rendering with hand-built `stats` dicts. Nothing exercises `table_stats` (the
   `relkind IN ('r','p','m')` filter, `NOT relispartition`, the PK `EXISTS`, skipping absent tables), `measured_note`
   or the `--dsn` branch of `main`. Those are the parts that decide what the diagram claims. *Verified:* I
   reverted `dictionary.py` to base; the whole test module then fails at import (`area_summary` missing), so the
   rendering tests do guard that file, but `stats.py` has no test that would fail if the filter or the PK check
   regressed. I checked its behaviour by hand with a read-only call (above), so it works today. *Fix:* a test that
   fakes `psycopg2.connect` (a cursor returning `[("a", True), ("b", False)]` for the catalog query and counts for the
   `count(*)` calls) and asserts the returned dict, plus a test of `measured_note` with a fixed `when`, and one of
   `main(["--dsn", ...])` with `table_stats` monkeypatched, asserting `STATS_NOTE` reaches the legend.

2. **`packages/erd/pyproject.toml:16-17` and `uv.lock`: the new `db` extra leaves the lockfile stale.** The PR adds
   `[project.optional-dependencies] db = ["psycopg2-binary>=2.9"]` but doesn't touch `uv.lock`. *Verified:*
   `uv lock --check` passes on the base commit `0ba4fcd2` and fails on the head ("The lockfile at `uv.lock` needs
   to be updated"). The `communityone-erd` entry still lists only loguru, numpy and pyyaml. CI is green, so it
   doesn't use `--locked`, but anyone running `uv sync --locked` or `uv lock --check` will fail. *Fix:* run `uv lock`
   and commit the change.

### 🔵 Nits / suggestions (Minor)
3. **`dictionary.py:78-86` and `area_title`: "N of M with a primary key" mixes two sources.** For measured tables it
   is Postgres's answer; for unmeasured ones it is the dbt declaration. The docs say so, but the diagram title does
   not. Elections reads "5 tables · 0 of 5 with a primary key" although none of the five is built here
   (`dim_candidate_contests`, `dim_election_divisions`, `fct_*` declare no key column). Likewise "Topics and tags"
   reads "8 of 8" but only 7 were measured (7 of 7 by Postgres, plus one declared). Consider counting the PK over
   measured tables only (as the row total does), or adding "declared" for the unmeasured part. No number is
   invented, so this is wording.
4. **`stats.py:24-37`: the connection is not read-only, has no statement timeout, and is never closed.** The tool
   runs `count(*)` on every mart, including 15 to 17 GB tables (about 2.5 minutes, as the PR says), against any DSN
   the caller passes. `with psycopg2.connect(...) as conn` ends the transaction but doesn't close the connection.
   *Fix:* `conn.set_session(readonly=True)` after connecting, close the connection (`contextlib.closing`), and
   consider a `--statement-timeout` so a lock wait can't hang a 25-minute run silently.
5. **`__main__.py:38-40`: counts are not a single snapshot.** Each table is counted in a separate statement, so
   tables that change during the run (the warehouse was being rebuilt at the time) are measured at different
   moments, while the legend gives one minute. The docs could say "about" or name the start time. Minor, since the
   legend already says it is when the counts were taken.
6. **The regenerated diagram contains a few more tables than the old one (108 vs 85).** That is main's marts moving
   on, not this PR, but it makes the `.drawio` diff unreviewable line by line. The PR says it rendered
   `marts_entity.drawio` in headless Chromium; I could not reproduce that here (see Test Coverage), so that claim
   is unverified. I did check the XML: 104 "N rows" labels (96 tables plus 8 area totals), 12 "rows not measured yet",
   9 area titles, one legend line each.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/566-erd-row-counts`; body says `Closes #566` and `Refs #567`. #566 and #567 both have Problem, Done when, Contract and Read first; #567 is an `action-item` for the 16 PK-less tables found. PR conventions check passes |
| Conventional Commits | Yes | `feat(erd): …` and `docs(erd): …`, both with the co-author trailer |
| No fabricated data | Yes | Scan above |
| New Python in `packages/` | Yes | New module is `packages/erd/src/erd/stats.py`; entry point stays `python -m erd`; nothing in `scripts/` |
| dbt for transformations | n/a | No SQL logic over data. The catalog query reads metadata and counts rows for a diagram; the transformation rule isn't engaged |
| Naming | n/a | No models or columns added |
| Keys | n/a | No `public` model changed; the PR reports the PK gap (#567) |
| Calendar years | n/a | None |
| Scope label matches filter | n/a | No `web_app` change |
| Match evidence on filtered tiles | n/a | No `web_app` change |
| Docs | Yes | `web_docs/docs/data-sources/marts-erd.md` updated; frontmatter and path unchanged; no new root `.md` |
| Telemetry and logging | Yes | The package logs with `loguru` (`logger.info` of measured vs modelled tables) |
| Tests | Partial | Rendering and `area_summary` covered; `table_stats`, `measured_note` and the `--dsn` path are not (finding 1) |
| Shared libraries | Yes | `packages/erd` tests run; no other package or `api/` imports `erd` (checked by grep); `uv.lock` is stale (finding 2) |

## Test Coverage
- **Run locally** (worktree code forced with `PYTHONPATH`):
  - `pytest packages/erd/tests`: 6 passed.
  - `ruff check packages/erd`: clean.
  - `uv lock --check`: passes on base, fails on head (finding 2).
  - Reverting `dictionary.py` to base makes the test module fail at import, restored afterwards.
  - `erd.stats.table_stats` called read-only against `localhost:5433/open_navigator` for four names: the view and
    the unknown model were omitted; the two tables came back with counts and correct PK flags.
- **Warehouse reproduction (read-only, `default_transaction_read_only=on`):** of 108 modelled marts, 96 are tables in
  `gold`, 2 are views (`event_place_geocoded`, `event_youtube_with_jurisdiction`) and 10 are absent. `public` has 11
  tables (all with a PK) and 74 views. 16 `gold` tables have no PK, 4 of them among the measured marts. Per-area
  table counts, measured counts and PK counts match the diagram titles. Row totals from `pg_class.reltuples` match
  the PR's exact counts for Jurisdictions (580,674) and are within about 1% elsewhere (estimates drift), e.g.
  Events and meetings 1,314,344 vs 1,313,971. I did not run `count(*)` on the 15 to 17 GB tables, so the exact
  totals for the large areas are unverified beyond the estimates.
- **Not run:** the 25-minute generator end to end, and the headless-Chromium render and the draw.io open in the test
  plan (the last is the PR's own unchecked reviewer item). No frontend or API files changed, so `tsc` was not needed.
- **Not covered by tests:** finding 1.

## Verdict
**approve-with-nits.** Nothing blocks the merge on correctness: the numbers are real, gaps stay gaps, and the checks are green. Please
add the `table_stats`/`measured_note`/`--dsn` test (finding 1) and regenerate `uv.lock` (finding 2) before merge, and consider the wording and
read-only-connection nits (3 and 4). Findings 3 to 6 can go into one `action-item` issue.
