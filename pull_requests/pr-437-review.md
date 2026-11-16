---
pr: 437
branch: feat/426-data-freshness-checks
title: "feat(dbt): check data freshness and scrape coverage, and report it nightly"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review in a fresh worktree; each finding traced in the code)
verdict: approve-with-nits
---

# PR Review: feat(dbt): check data freshness and scrape coverage, and report it nightly

## Summary
Adds `dbt source freshness` limits on the YouTube catalog, transcripts, analyses, the Epoch load and a new
`intermediate_runtime.int_events_channels` source; warn-severity `dbt_utils.recency` tests tagged `freshness` on
`event_documents`, `event_meeting`, `event_decision`, `jurisdiction_state_aggregate` and `data_center_site`; a coverage
test on the homepage scrape; a nightly-crawl step that runs them; and a docs page. `dbt parse` passes, the five recency
tests and the singular test list under `tag:freshness`, and every timestamp column they read exists in its model or
migration. The nightly-crawl commands ran the wrong dbt and had a broken second `cd`; both are fixed on the branch.
Approve with nits.

## Scope of Change
- Files changed: 8 (+196 / -0)
- Areas touched: dbt_project / web_docs / agents
- Commits:
  - 3afdf015 feat(dbt): check data freshness and scrape coverage, and report it nightly
  - d72d1873 fix(dbt): run the nightly freshness checks with the pinned dbt and in one shell (review fix)
- Range reviewed: `fb865cc2..3afdf015`, then the fix

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker changes) |

CI was read on 3afdf015; the fix commit triggers a new run.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean (no `api/` or `web_app/` changes).
- Personal data: clean.
- Destructive or bulky data changes: clean (tests and source config only; nothing writes to the warehouse).

## Strengths
- Warn severity on the served-table tests, with the reason written down: a stale table can't skip the rest of
  `dbt build`.
- The coverage test catches the failure that timestamps can't (a scrape that writes fresh rows with no links).
- `int_events_channels` is declared as a separate `intermediate_runtime` source, so it doesn't collide with the dbt
  models of similar names (`int_events_channels_registry`, `int_events_channels_enriched`).
- New tests use the `arguments:` form, so they add none to the 126 existing
  `MissingArgumentsPropertyInGenericTestDeprecation` warnings.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Fixed (d72d1873).** `.claude/commands/nightly-crawl.md`, step 4: the new lines ran `uv run dbt ...` from
   `dbt_project/`, and so did the existing `uv run dbt build` line in the same step. `dbt_project/` has no
   `pyproject.toml` or `.venv`, so `uv run` resolves to the root `.venv` (checked: `sys.prefix` is the root `.venv`),
   whose dbt is 1.12.0-b1, not the 1.11.9 in `dbt_project/.venv_dbt` that the runbooks use (raised first in #399's
   review). All three now call `.venv_dbt/bin/dbt` from `dbt_project/`, and `data-freshness.md` shows the same commands.

### 🔵 Nits / suggestions (Minor)
1. **Fixed (d72d1873).** The new code block put `cd dbt_project && ...` on two lines. Run in one shell, the second
   `cd` fails once the first has moved into `dbt_project/`. Now one line.
2. **Fixed (d72d1873).** The `bronze_event_youtube` source comment said `loaded_at` "isn't set on new rows". #440
   (issue #429) makes the loaders set it, so the comment now points at #429 and keeps `last_updated` (older rows stay
   NULL).
3. **Left.** `jurisdiction_state_aggregate.last_updated` is `CURRENT_TIMESTAMP` at build time, so its recency test
   measures when the rollup was last rebuilt, not when its inputs changed. That matches the docs ("stats rollup older
   than 7 days"), but a rebuild over stale inputs passes.
4. **Left.** The page links to `context-engineering.md`, which arrives in #436. The body says to merge #436 first.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `feat/426-data-freshness-checks`; `Closes #426`; the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | |
| New Python in `packages/` | n/a | |
| dbt for transformations | Yes | All checks are dbt source freshness and tests |
| Naming | Yes | |
| Keys | n/a | No new `public` models |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | `web_docs/docs/development/data-freshness.md`, kebab-case, frontmatter |
| Telemetry and logging | n/a | |
| Tests | Yes | The change is tests; the PR reports a run on the local warehouse |
| Shared libraries | n/a | |

## Test Coverage
Ran locally: `dbt parse` (dbt 1.11.9, `dbt_packages` symlinked from the main checkout, then removed), clean apart from
existing warnings. `dbt ls --select tag:freshness` lists the five recency tests and
`assert_homepage_scrape_found_links`. The manifest shows each source's `loaded_at_field` and warn/error limits as
documented. Checked that every column read exists (`created_at` in `event_documents`, `extracted_at` in `event_meeting`
and `event_decision`, `last_seen_on` in `data_center_site`, `loaded_at` in migration 071's `int_events_channels`) and
that the scraper writes `social_media.<platform>` as arrays, which `jsonb_array_length` needs. Not run here: `dbt source
freshness` and `dbt test` against the warehouse (a long job is using the main checkout); the PR reports both.

## Verdict
Approve with nits. The runbook dbt binary and shell fix are in; merge after #436.
