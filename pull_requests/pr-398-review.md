---
pr: 398
branch: feat/392-publish-crawled-agendas
title: "feat(meetings): publish agendas and minutes from the nationwide crawl"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (Claude Code review agent, read-only; findings reproduced against a throwaway Postgres 16)
verdict: request-changes
---

# PR Review: feat(meetings): publish agendas and minutes from the nationwide crawl

## Summary
The PR adds `staging.stg_scraped_meeting_documents`, a view over the three homepage-crawl bronze tables. It unions that view
into `public.event_meeting_document` with `source = 'scraped_meetings'`, limits the SuiteOne model's "attachment" branch
to SuiteOne cities, and adds a `python -m scrapers.meetings.doctext` CLI that extracts text for the same documents. The
SQL is sound. The two staging models really are disjoint, the grain holds, year-only placeholder dates are kept out of
the new model, and the CLI selects exactly the rows the staging model publishes. I built it with dbt and checked the
CLI against the view on seeded rows. Three things still need fixing:
- One of the issue's Done-when checks isn't met: the Neon 480 MB budget dry-run was never run or reported.
- Because school districts are now unioned in, a 7-digit school-district geoid can collide with a place geoid and
  attach a school board's agenda to a city's meeting.
- A SuiteOne city can now show the same agenda twice, once under a broken, un-canonicalized portal URL.

**Request changes.**

## Scope of Change
- Files changed: 9 (+522 / -24). Nothing generated except the regenerated ODCS contract, which is counted.
- Areas touched: dbt_project, packages (scrapers)
- Commits:
  - `68e8fe79` feat(meetings): publish agendas and minutes from the nationwide crawl
- Range reviewed: `61d2a870..68e8fe79`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | ✅ success |
| Documentation Build (Docusaurus) | ✅ success |
| Backend Tests (Python) | ✅ success |
| API Types (OpenAPI -> TypeScript) | ✅ success |
| PR conventions (linked issue) | ✅ success |
| Docker Build Test (Full Stack) | ⏭️ skipped (not required; no Docker changes) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No keys, DSNs or cookies. The DSN comes from `_resolve_dsn()` at runtime.
- **Fabricated data in a served path:** clean for the new code. The new model excludes `manifest_year_only` (January 1)
  dates, and the CLI stores `empty_needs_ocr` rather than inventing text. One pre-existing leak sits in the SuiteOne
  attachment branch, which this PR edits. See 🟡 3.
- **Personal data:** clean. These are public meeting records.
- **Destructive or bulky data changes:** clean. Nothing touches `data/cache/`, no raw files are committed, and every
  warehouse change goes through dbt. The live test drops `bronze.bronze_meeting_document_text`, but only on the
  database named by `TEST_DATABASE_URL`, and only with `RUN_LIVE_TESTS=1`.

## Strengths
- The two staging models are disjoint by construction. The new model takes only `doc_type IN ('agenda','minutes')`
  without `suiteone_listing`. The SuiteOne model takes only `suiteone_listing` agenda/minutes or `doc_type='unknown'`.
  The bronze `UNIQUE (jurisdiction_id, url_sha256)`, and a jurisdiction belonging to a single type table, keep the
  shared md5 surrogate unique across the union. dbt `unique` passed on both staging models and the mart.
- No Fabricated Data was handled on purpose. The loader's `manifest_year_only` path stamps January 1, and it's excluded.
  I read every source `pick_meeting_date` can emit (`anchor_text`, `filename*`, `month_day_year_text`, `url_query:*`,
  `mdy_short_year`), and each one parses a real day.
- The `doctext` filter mirrors the staging filter predicate for predicate. Run against the seeded tables, its selection
  returned the same 4 `(jurisdiction_id, url_sha256)` pairs as `stg_scraped_meeting_documents`.
- Narrowing the attachment branch stops the whole country's unclassified PDFs from landing in the mart labelled
  `suiteone`.
- The CLI sits in `packages/` as `python -m scrapers.meetings.doctext`, logs with loguru, and can resume. The live
  test covers published, year-only and SuiteOne rows.

## Findings

### 🔴 Blocking (Critical)

**1. The issue's Neon Done-when check isn't met.** Files: `dbt_project/models/marts/event_meeting_document.sql:108-127`
and `packages/hosting/src/hosting/neon/sync_public_to_neon.py:158`.
- **What's wrong:** Issue #392 says it's done when "The rows published to Neon keep the 480 MB budget
  (`sync_public_to_neon --dry-run` reported in the PR)". The PR body says the dry-run wasn't run.
- **Why it matters:** `event_meeting_document` is in `CIVIC_SERVING`, and it's copied to Neon whole, including `content`
  and the stored `content_tsv` tsvector. `event_documents` had to be slimmed to cues-only (content and tsvector NULLed)
  for exactly this reason. Once the next `dbt build` runs, every day-dated agenda/minutes PDF in the three crawl tables
  lands in the mart. Each `doctext --state` run then adds full text plus a tsvector. The sync's budget guard
  (`budget_problem`, exit 4) stops Neon from going over the cap. But it refuses the *whole* sync, so an oversized mart
  stalls every production publish, not only this table.
- **Second effect:** narrowing the attachment branch removes any `attachment` rows for non-SuiteOne cities that
  production serves today. The PR doesn't say how many there are.
- **How I verified it:** I read the issue's Done-when, the PR body, and the `CIVIC_SERVING` list. No dedicated slim
  loader exists for this table.
- **Fix:** Run `python -m hosting.neon.sync_public_to_neon --dry-run` against the home warehouse after building the
  mart. Report the projected size and row counts by `source` and `document_type`, before and after. If it doesn't fit,
  ship crawled docs without `content` and `content_tsv` on Neon (for example a slim projection or a cap per state).
  Otherwise, change the PR to `Refs #392` and split the budget item into its own issue.

### 🟡 Should fix (Important, non-blocking)

**2. A school-district document can attach to a city's meeting through a geoid collision.** Files:
`dbt_project/models/marts/event_meeting_document.sql:188,211`, `dbt_project/models/staging/stg_scraped_meeting_documents.sql:51-56`,
and `api/routes/jurisdiction_meeting_documents.py:67`.
- **What's wrong:** School-district GEOIDs (state plus 5-digit LEA code) and place GEOIDs (state plus 5-digit place
  code) are both 7 digits, in overlapping code spaces. `core_lib.jurisdictions.infer_jurisdiction_type_from_geoid`
  already treats any 7-digit geoid as "municipality".
- **Where it bites:** The mart's preferred jurisdiction match is `m.geoid = d.census_geoid`. Until this PR, only
  municipality rows reached it. With school districts unioned in, a district whose geoid equals a city's place geoid
  matches that city's meeting whenever the date and `body_key` agree. School boards commonly hold "Work Session" and
  "Finance Committee" meetings, which give the keys `work_session` and `finance`. The same collision mixes the
  district's documents into the city's `/jurisdictions/{geoid}/meeting-documents` list, because that endpoint filters
  on `OR census_geoid = $1`.
- **How I verified it:** I seeded `some_district_0177256` (a school-district row with geoid `0177256`) with a "Board
  Finance Committee Agenda" on 2026-10-07. After the build, the mart gave it `event_meeting_id = 1`, Tuscaloosa's
  Finance Committee meeting. Collisions in real data weren't checked (no warehouse here). Across roughly 19k places and
  13k districts, though, some are near certain.
- **Fix:** Carry `jurisdiction_type` through to the mart and allow the geoid match only within the same type. Or match
  on `d.jurisdiction_id = em.jurisdiction` when `event_meeting.jurisdiction` is a canonical id. Either way, add a dbt
  test with a colliding school-district row.

**3. A SuiteOne city can list the same agenda twice, one copy with a broken URL.** Files:
`dbt_project/models/staging/stg_scraped_meeting_documents.sql:69-70,85`.
- **What's wrong:** The new model excludes SuiteOne *rows*, not SuiteOne *jurisdictions*. When Tuscaloosa's homepage
  crawl links a portal PDF under a variant URL, both rows are published. The variant can be the dated-label form
  `.../GetAgendaFile/10/7/26%20Agenda?aid=1`, which has a different `url_sha256` and a `doc_type` of `agenda` from the
  anchor classifier. The variant is published as `source='scraped_meetings'` with the raw `url` as `document_url`. The
  SuiteOne model rewrites that label form (`regexp_replace` at `stg_suiteone_meeting_documents.sql:97-102`) precisely
  because embedded slashes and spaces return 404.
- **How I verified it:** I seeded the SuiteOne listing row and the crawled variant for the same meeting. The mart
  returned two `agenda` rows, both linked to `event_meeting_id = 1`. The `scraped_meetings` row carried the
  un-rewritten URL.
- **Fix:** In `stg_scraped_meeting_documents`, drop rows whose URL matches the SuiteOne portal pattern (`/event/Get(Agenda|Minutes|Document)File/`),
  or drop crawled agenda/minutes rows for jurisdictions that have SuiteOne listing rows (the same subquery the
  attachment branch now uses). At minimum, apply the same URL canonicalization.

**4. SuiteOne attachments still serve a made-up January 1 date.** File:
`dbt_project/models/staging/stg_suiteone_meeting_documents.sql:27-28,103`.
- **What's wrong:** This PR edits the attachment branch, and that branch still passes `meeting_date` straight through
  as `doc_date`. The loader stamps January 1 of the folder year (`manifest_year_only`) on likely-meeting PDFs that have
  no parsed day. Those attachments are served as, say, `doc_date = 2025-01-01`, and the API groups them as a meeting on
  that date. That breaks No Fabricated Data, the rule the new model was written to respect. The header comment says
  attachments carry "NULL/non-listing meeting_date (-> NULL doc_date)", but non-listing dates aren't NULLed.
- **How I verified it:** I seeded a Tuscaloosa `unknown` document with `meeting_date = 2025-01-01` and
  `manifest_year_only`. The mart served `attachment | 2025-01-01`.
- **Fix:** Use `case when meeting_date_source = 'manifest_year_only' then null else meeting_date end as doc_date`
  (better still, NULL every non-`suiteone_listing` date for attachments, or keep only real day sources) and correct the
  comment. If you'd rather keep it out of scope, open an `action-item` issue and link it from the PR.

### 🔵 Nits / suggestions (Minor)

**5. Failed downloads are never retried.** File: `packages/scrapers/src/scrapers/meetings/doctext.py:64,116`.
`text_for` records transient failures as `extraction_method='error'` (and non-PDF responses as `not_pdf`), and the
`NOT EXISTS` then skips them on every later run. The docstring's "resumes where it stopped" therefore also means "never
retries a timeout". Add `--retry-errors`, which selects rows where `extraction_method IN ('error')`, or leave errors
out of the skip.

**6. `--doc-types` can drift from what's published.** File: `packages/scrapers/src/scrapers/meetings/doctext.py:185`.
`--doc-types unknown` (or any value) widens the selection beyond `doc_type IN ('agenda','minutes')`, so the CLI would
extract text for documents the staging model never publishes. Restrict the value to `{agenda, minutes}`.

**7. A dry run still writes DDL.** File: `packages/scrapers/src/scrapers/meetings/doctext.py:138`. `--dry-run` runs
`CREATE TABLE IF NOT EXISTS` even though the help text says "write nothing". Either skip the DDL on a dry run (and skip
`NOT EXISTS` when the table is absent), or reword the help text.

**8. The drift test only checks substrings.** File: `packages/scrapers/tests/test_meetings_doctext.py:11-20`.
`test_select_covers_every_crawl_table_and_mirrors_the_staging_filter` checks substrings, not behaviour, so the
"keep in step" comment is the only guard. The live test could also build the staging SQL over the same seeded rows and
compare the two sets. I did this by hand (4/4 match).

**9. Private names imported across modules.** File: `packages/scrapers/src/scrapers/meetings/doctext.py:32-33`. The
module imports the private names `_DDL`, `_TEXT_TABLE`, `_UA`, `_UPSERT` and `_resolve_dsn` from `scrapers.suiteone`.
Move them into a small shared module, for example `scrapers.meetings.text_store`, so a SuiteOne refactor can't break
the nationwide CLI without anyone noticing.

**10. Undocumented staging columns.** File: `dbt_project/models/staging/_staging.yml:2373-2418`. The yml doesn't
document `jurisdiction_id`, `census_geoid`, `url_sha256`, `meeting_title`, `body_key` or `created_at`. `jurisdiction_type`
is an addition to the issue's Contract, which is fine, but add a dated line to #392 noting it.

**11. Several bodies can collapse into one meeting group.** Most crawled county and school-district titles map to
`body_key = NULL`. `_group_meeting_documents` then puts every NULL-body document on the same date into one "meeting"
group (`api/routes/jurisdiction_meeting_documents.py:72-104`). That's acceptable for now, but worth a follow-up issue.

**12. Formatting.** `ruff check` passes. `ruff format --check` would reformat both new files, but the package's existing
files aren't formatted either and CI doesn't enforce it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ⚠️ | The branch name, `Closes #392`, and the issue's four parts are all fine. One Done-when check is unmet (🔴 1). |
| Conventional Commits | ✅ | One commit, `feat(meetings): …`, with the co-author trailer |
| No fabricated data | ⚠️ | The new model is clean. The edited SuiteOne attachment branch still serves January 1 dates (🟡 4). |
| New Python in `packages/` | ✅ | `python -m scrapers.meetings.doctext`. Nothing added to `scripts/`. |
| dbt for transformations | ✅ | All filtering and unioning is in dbt. Python only does extraction. |
| Naming | ✅ | `state_code` and `state` are both present. No `dim_` or `fact_` names. |
| Keys | ✅ | The mart's PK and FK are unchanged and enforced (contract plus the `relationships` test passed). The staging view isn't in `public`. |
| Calendar years | n/a | Only real `date` columns |
| Scope label matches filter | n/a | No UI change. Note the geoid filter mixing in 🟡 2. |
| Match evidence on filtered tiles | n/a | No UI change. `data_center_agenda_item` keeps its `ts_headline` evidence over the new rows. |
| Docs | ✅ | No new docs. The how-to guide is in #391's PR. |
| Telemetry and logging | ✅ | loguru in the CLI. No FastAPI changes. |
| Tests | ⚠️ | The CLI has unit tests and a live test. No dbt test covers the geoid collision or the duplicate SuiteOne docs. |
| Shared libraries | ✅ | Only additions to `scrapers`. The `scrapers` suite passed (see below). |

## Test Coverage
- **CLI tests:** `scrapers.meetings.doctext` has unit tests (SQL shape, local-PDF reader) and a live test (a real PDF in
  Postgres; it checks published, year-only and SuiteOne rows, plus resumability).
- **dbt tests:** `unique` and `not_null` on the new surrogate, `accepted_values` on `jurisdiction_type`, `document_type`
  and the mart's `source`, and `not_null` on `doc_date`.
- **Not tested:** cross-type geoid collisions, duplicate SuiteOne docs from the crawl, the narrowing of the attachment
  branch, and Neon size.

Run locally:
- **Package tests:** `pytest packages/scrapers/tests` gave 85 passed and 1 skipped, with this branch's `src` on
  `PYTHONPATH`.
- **Live test:** run with `RUN_LIVE_TESTS=1`, `TEST_DATABASE_URL` pointing at a fresh database, and
  `test_meetings_doctext.py`. 3 passed.
- **Lint:** `ruff check` on the new Python is clean.
- **dbt build:** `dbt build --select stg_suiteone_meeting_documents stg_scraped_meeting_documents event_meeting_document`
  ran against a throwaway Postgres 16. It used migration 020's bronze tables plus my own seed: SuiteOne listing rows, a
  crawled variant of a SuiteOne URL, a year-only attachment, a non-SuiteOne `unknown` PDF, a day-dated city agenda, a
  year-only minutes PDF, a school district with a colliding geoid, and county minutes. Result: PASS=29, ERROR=0, with
  the contract enforced. The output confirmed the exclusions and reproduced 🟡 2, 🟡 3 and 🟡 4.
- **Downstream:** `dbt ls --select stg_scraped_meeting_documents+ stg_suiteone_meeting_documents+` lists
  `event_meeting_document` and `data_center_agenda_item`. The home warehouse and Neon weren't reachable from this
  session, so I measured no real row counts or sizes.

## Verdict
**Request changes.** Before merge:
- Run `sync_public_to_neon --dry-run` on the built mart and report the size and row deltas, or slim the Neon copy, or
  re-scope the PR to `Refs #392` (🔴 1).
- Stop school-district documents from matching city meetings and city geoid lookups through geoid collisions (🟡 2).
- Keep SuiteOne-portal URLs out of the crawl model, or canonicalize them (🟡 3).
- NULL the `manifest_year_only` dates in the attachment branch you edited, or file an `action-item` issue for it (🟡 4).

The nits can follow in this PR or later ones.
