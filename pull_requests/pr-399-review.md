---
pr: 399
branch: docs/391-nationwide-meeting-crawl
title: "docs(meetings): document the nationwide agenda and YouTube meeting crawl"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review; every finding traced in the code)
verdict: request-changes
---

# PR Review: docs(meetings): document the nationwide agenda and YouTube meeting crawl

## Summary
The PR adds `web_docs/docs/guides/crawling-meetings-nationwide.md`, a runbook for the nationwide agenda/minutes crawl,
manifest load, text extraction, YouTube channel promotion, the national YouTube runner and the Neon publish. It also
puts an "Outdated" banner on `loading-meeting-data.md`. The page builds cleanly, follows the docs rules, and most
commands, flags, paths and table names match the code, including the parts that depend on #397 (#393) and #398 (#392).
Five statements would mislead someone following the runbook. The step 1 query names a column that doesn't exist. The
recommended `--retry-failed-shallow` usage fails. The channels promoted in step 4 never reach the national YouTube
runner in step 5. Step 6 doesn't rebuild `data_center_agenda_item`. Step 6 also never syncs transcripts. None of these
trips a blocking scan, but the page is a runbook and these are its main steps, so the verdict is **request-changes**.

## Scope of Change
- Files changed: 2 (+216 / -0)
- Areas touched: web_docs
- Commits:
  - `5a49d3997` docs(meetings): document the nationwide agenda and YouTube meeting crawl
  - `3c94bd9a2` docs(meetings): describe the crawl after the publish and loader fixes
- Range reviewed: `61d2a870..3c94bd9a`
- Code checked against: `main` at the merge base for the crawl, channel sync, YouTube runners and `hosting.neon`;
  `origin/fix/393-loader-keeps-suiteone-rows` (`7681446e`) for the loader;
  `origin/feat/392-publish-crawled-agendas` (`68e8fe79`) for `scrapers.meetings.doctext` and
  `stg_scraped_meeting_documents` / `event_meeting_document`.

## CI Status
| Check | Status |
|---|---|
| Documentation Build (Docusaurus) | ✅ success |
| Frontend Build (TypeScript + Vite) | ✅ success |
| Backend Tests (Python) | ✅ success |
| API Types (OpenAPI -> TypeScript) | ✅ success |
| PR conventions (linked issue) | ✅ success |
| Docker Build Test (Full Stack) | skipped (no Docker changes; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Only environment variable names appear (`PROXY_USER_NAME`, `PROXY_PASSWORD`, `SCRAPED_MEETINGS_ROOT`), with no values.
- **Fabricated data in a served path:** clean. The PR is docs only. The numbers it gives (512 MB cap, 480 MB budget, 80/80 defaults, `N=10`, `DELAY=10`) match the code.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. The page tells readers never to delete `data/cache/` and never to pass `--apply-ddl` on a populated warehouse.

## Strengths
- The commands, flags and defaults for the crawl, loader, doctext, channel sync, SuiteOne and the Neon sync mostly match the argparse code: `--batch-from-db`, `--type all`, `--concurrency`, `--timeout`, the 80-page and 80-PDF defaults, `--shallow-max-pages` 6, `--states`, `--dry-run`, `--limit`, `--portal-url`, `--jurisdiction-id`, `--doc-types`, the exit code 4 and the `--max-mb` default of 480.
- `python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction` imports and runs from the repo root (`scripts/__init__.py` and `scripts/discovery/__init__.py` exist).
- The page states the publish filter exactly as `stg_scraped_meeting_documents` (#392) implements it: agenda or minutes only, a real day, `manifest_year_only` excluded, SuiteOne rows excluded.
- The `--apply-ddl` warning is correct (migration 020 drops and recreates all three scraped meetings tables). The loader's behaviour after #393 (it deletes only its own rows and its insert skips conflicts) is described accurately.
- It follows the rule against new `scripts/` code: it marks the three `scripts/discovery/` modules as legacy and sends new features to `packages/scrapers`.
- The banner on `loading-meeting-data.md` is the right size and links the new page.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)

1. **`web_docs/docs/guides/crawling-meetings-nationwide.md:61-64`: the step 1 query selects a column that doesn't exist.**
   `intermediate.int_jurisdiction_websites` has no `jurisdiction_type` column. Its final `SELECT`
   (`dbt_project/models/intermediate/int_jurisdiction_websites.sql`, the last ~25 lines) returns `website_record_key,
   website_source, domain_name, website_url, domain_type, jurisdiction_category, organization_name, agency, city,
   state_code, state, jurisdiction_id, ingestion_date, transformed_at`. Pasting the query fails with `column
   "jurisdiction_type" does not exist`. The table also has one row per source (GSA, USCM, league, NCES, NACo, Wikidata,
   override), so `count(*)` overstates homepages. The crawl takes `DISTINCT ON (jurisdiction_id)`. **Verified:** read
   the model's final projection. The warehouse on `localhost:5433` was not reachable from the review environment, so
   the query was not run. **Fix:** `select state_code, jurisdiction_category, count(distinct jurisdiction_id) ...
   group by 1, 2`. Splitting `jurisdiction_id` on `_` won't work because canonical ids are slugs such as
   `tuscaloosa_0177256`.

2. **`crawling-meetings-nationwide.md:96` and `:200`: `--retry-failed-shallow` doesn't work as the page presents it.**
   (a) The CLI rejects it unless `--from-db` is passed and `--type` is a concrete type: `main()` exits with
   "--retry-failed-shallow requires --from-db" and with "requires a concrete --type (e.g. county), not 'all'"
   (`scripts/discovery/comprehensive_discovery_pipeline_jurisdiction.py:3796-3801`). The nightly-order line ("or
   `--retry-failed-shallow` for states already crawled"), copied onto the step 2 command (`--batch-from-db ... --type
   all`), exits at once ("Choose only one of --batch-from-db or --retry-failed-shallow"). (b) Even with the right flags,
   `collect_retry_geoids_from_scraped_manifests` globs `{root}/{ST}/{type}/{type}_*/_manifest.json` (line 1303). The
   crawl now writes canonical folders named `{place_slug}_{geoid}`
   (`llm.gemini.transcript_cache_paths.scraped_meetings_jurisdiction_dir`), so the retry finds only legacy
   `county_01001`-style folders. **Verified:** against a scratch tree holding `AL/municipality/tuscaloosa_0177256` and
   `AL/municipality/municipality_0100124`, both with zero-page manifests, the function returned `['0100124']` and
   missed Tuscaloosa. **Fix:** in the doc, show the full form (`--retry-failed-shallow --from-db --state AL --type
   municipality`, one run per type) and say it only finds legacy-named folders until the glob is fixed. Open an
   `action-item` issue for the glob (it's a code bug, out of scope here), and for `--type school` not being mapped to
   the `school` segment / `school_district_` prefix on this path.

3. **`crawling-meetings-nationwide.md:27`, `:136-138`, `:148-149`: the channels promoted in step 4 don't feed the YouTube runner in step 5.**
   `sync_bronze_jurisdiction_youtube_from_meetings_scrape.py` writes to `intermediate.int_events_channels_candidates`
   and `intermediate.int_events_channels` (its docstring; `scripts/discovery/int_events_channels_persist.py`). The
   national runner does two things that bypass those tables. (a) It builds its plan only from jurisdictions that
   already have video rows in `bronze.bronze_event_youtube` (`api/batch_jobs/batch_job_status.py:245-300`, `EXISTS
   (SELECT 1 FROM bronze.bronze_event_youtube ...)`). (b) It catalogs each planned jurisdiction with
   `--channel-source counties-scraped|municipalities-scraped`
   (`packages/scrapers/scripts/youtube_run_priority_states_last_n.sh`, `resolve_catalog_channel_source`). Those sources
   read `bronze.bronze_jurisdictions_{counties,municipalities}_scraped`
   (`load_youtube_events_to_postgres.py:1222-1234`), not `int_events_channels`. A newly promoted channel for a
   jurisdiction with no videos yet is never picked up. "Promote them into the channel list the YouTube crawl reads" and
   "Its YouTube channel links also feed the YouTube crawl" are therefore wrong as written. The runner also reads
   *video* rows, not "channels in `bronze.bronze_event_youtube`" (line 148). **Verified:** traced the plan query and the
   catalog channel source. **Fix:** document a seeding step that uses `int_events_channels`, for example a bulk catalog
   with the `auto` channel source (`STATES=AL ROUND_ROBIN=0 ./packages/scrapers/scripts/youtube_run_priority_states_last_n.sh
   catalog`, which runs `load_youtube_events_to_postgres.py --states AL --channel-source auto`). Run it once to confirm
   before documenting it. Or state the gap and open an `action-item` issue.

4. **`crawling-meetings-nationwide.md:172`: step 6 doesn't rebuild `data_center_agenda_item`, though the page says crawled text feeds it (`:28`, `:33`, `:130-131`).**
   The selector `+meeting_browse +event_decision +event_meeting_document +job_claim` builds only upstream models.
   `data_center_agenda_item` sits *downstream* of `event_meeting_document`, and no model refs it. Marts are
   `incremental` tables in `gold` (`dbt_project.yml`), so it stays stale. `sync_public_to_neon` then copies the stale
   table to Neon (it's in the serving list at `sync_public_to_neon.py:220`). **Verified:** grep found no model that
   refs `data_center_agenda_item`; it refs `event_meeting_document`. **Fix:** add `data_center_agenda_item` to the
   selector, or use `event_meeting_document+`.

5. **`crawling-meetings-nationwide.md:173` and `:29`: transcripts are dry-run only and launch-scoped.**
   Step 6 runs `hosting.neon.sync_event_documents_to_neon --dry-run` but never the real sync. `event_documents` is left
   out of `sync_public_to_neon` on purpose (`DEDICATED_LOADER`, lines 97-104 and 159-160). New YouTube transcripts (the
   cues the meeting page reads) therefore never reach Neon by following the page. The loader is also limited to
   `LAUNCH_STATES` (default `AL,GA,MA,WA`, `sync_event_documents_to_neon.py:78-81`). Its docstring warns that
   `--no-launch-scope` exceeds the free tier. The table row "YouTube crawl, all states → Yes" needs that qualifier.
   **Verified:** read both sync modules. **Fix:** either add the real `sync_event_documents_to_neon` run (and say that
   only launch states ship), or explain why it's dry-run only. Qualify line 29.

### 🔵 Nits / suggestions (Minor)

6. **`crawling-meetings-nationwide.md:166`: "Each new video is one analysis call" undercounts.** With `--newest`,
   `llm.gemini.meeting_transcript_policy.run_pipeline` forces `run_part_2 = True` (line ~1473). Each video then makes a
   Part 1 call and a Part 2 call (`stage="part1"` and `stage="part2"` usage rows). Say "two Gemini calls per video
   (analysis + report)".

7. **`crawling-meetings-nationwide.md:98-100`: some flags only apply to single-jurisdiction runs.**
   `--meeting-seed-urls` and `--civicclerk-tenant` (and `--contact-seed-urls`) are attached only when exactly one job
   runs (`main()`, `if len(jobs) == 1`). With `--batch-from-db` they're dropped without a warning. The `--geoid` row
   also needs `--state`, which is `required=True`. Add "single jurisdiction only (`--geoid ... --state ...`)" to these
   rows.

8. **`crawling-meetings-nationwide.md:56`, `:67-68`: smaller details in step 1.** The source list leaves out Wikidata
   (`wikidata_rows` is unioned in the model). After `dbt seed --select jurisdiction_website_url_overrides`, the seed's
   own description says to rerun `dbt run --select int_jurisdiction_websites`. Say so, or point back to the step 1
   build.

9. **Issue #391: the changed "Done when" isn't recorded on the issue.** #391 asks the page to say that crawled agendas
   "do not reach `public.event_meeting_document` yet". After #392 the page correctly says the opposite, and the PR body
   explains why. `AGENTS.md` says the issue should get a dated line rather than leave the change only in the PR. Add a
   comment like "2026-11-16: superseded by #392 ..." to #391.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | Branch `docs/391-nationwide-meeting-crawl`; body `Closes #391`; #391 has Problem, Done when, Contract, Read first. The changed Done-when has no dated line on the issue (nit 9). Follow-ups from findings 2 and 3 should become `action-item` issues |
| Conventional Commits | ✅ | Both commits use `docs(meetings): ...` with the co-author trailer |
| No fabricated data | ✅ | Docs only. The figures quoted match the code |
| New Python in `packages/` | ✅ | No code. The page sends new crawl features to `packages/scrapers` |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | ✅ | `web_docs/docs/guides/`, kebab-case, lowercase, frontmatter (`title`, `description`, `sidebar_position`); no root `.md`; links and anchor resolve |
| Telemetry and logging | n/a | |
| Tests | n/a | Docs only. The build is the test |
| Shared libraries | n/a | |

## Test Coverage
Docs only, so the docs build is the check. Run locally with `cd web_docs && npm run build`: success. There are no
broken-link or broken-anchor warnings for `crawling-meetings-nationwide` or the banner link. The remaining warnings are
on other pages and were there before this PR. The CI Documentation Build is green too. No Python changed, so `pytest`
and `ruff` don't apply. The retry-glob behaviour (finding 2) was reproduced with a short Python call against a scratch
directory. The warehouse (`localhost:5433`) didn't respond, so the SQL in step 1 was checked against the model source,
not run.

## Verdict
**request-changes.** Fix findings 1 to 5 before merge: the step 1 query, the `--retry-failed-shallow` usage, the step
4→5 channel claim, the `data_center_agenda_item` rebuild, and the transcript sync and launch scope. Each one is a
wording or command change in the guide. Open `action-item` issues for the two code gaps behind findings 2 and 3. Keep
the merge order the PR states: #393's PR (#397), then #392's (#398), then this one. The page describes behaviour that
exists only on those branches.
