---
pr: 532 (branch review; PR not open yet, expected next after #544)
branch: feat/532-dc-community-meetings
title: "feat(dc): find company-hosted data center community meetings in news and press releases"
author: jcbowyer
reviewed_at: 2026-11-17
reviewer: coordinator (read-only; every finding traced in code, compiled SQL or a read-only query)
verdict: request-changes
---

# PR Review: feat(dc): find company-hosted data center community meetings in news and press releases

## Summary
The branch adds a free, deterministic pipeline for company-hosted data center meetings: a polite loader
(`python -m ingestion.data_centers.community_events`: GDELT DOC API, Google News RSS gated by robots.txt, and
company press-release feeds) lands verbatim items in bronze; dbt matches the host (`master_org_id`), project,
meeting kind and a stated date, groups articles into events and publishes `data_center_community_event`,
`_source` and `_recording` with PK/FK; a VPN-guarded YouTube search lands recording candidates; and the API and
`/data-centers` page add **Company meetings** and **Projects** (with a timeline). The structure, politeness,
host labelling and empty states are good, and the local checks pass. But the date extraction takes the
**first** date in the text, and a press release opens with its dateline ("DALLAS, Oct. 2, 2026 --"), so a
company-feed event would be served with the release date as its "stated" meeting date. That is a wrong date
shown as a fact, so this is request-changes. Two smaller date and snippet bugs and missing SQL tests should be
fixed with it.

## Scope of Change
- Files changed: 27 (+3,220 / -1, excluding the generated `web_app/src/lib/api.types.ts`, +364)
- Areas touched: api / web_app / web_docs / dbt_project / packages (ingestion, hosting) / data contracts
- Commits: `784b1b3b` feat(dc): find company-hosted data center community meetings in news and press releases
- Range reviewed: `415529e7..784b1b3b` (`feat/531-dc-companies-projects...HEAD`; the #531 commits are PR #540)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | not run (no PR yet); local `npx tsc --noEmit` clean |
| Documentation Build | not run (no PR yet) |
| Backend Tests | not run (no PR yet); local pytest 48 passed, 3 skipped |
| API Types | not run (no PR yet); `api.types.ts` regenerated in the diff |
| PR conventions | not run; the PR body must say `Closes #532` (the commit says only `Refs #530`) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. `_dsn()` falls back to `POSTGRES_PASSWORD or "password"` for localhost, the existing
  local-warehouse default, not a real credential.
- **Fabricated data in a served path:** no invented numbers or placeholder figures. Empty and missing-relation
  states are explicit ("No company-hosted data center meetings found for …", "Date not stated"). The
  misdated-event bug below serves a real date with the wrong meaning; it is listed as a Blocking finding.
- **Personal data:** clean. The User-Agent names the project and repository only. Public news and press releases.
- **Destructive or bulky data changes:** clean. The loaders only `CREATE TABLE IF NOT EXISTS` and upsert into
  bronze; nothing touches `data/cache/` or `event_documents`.

## Strengths
- The owner's rules hold. No LLM and no paid calls. News comes only from GDELT (6 s spacing, 429 and transport
  backoff) and Google News RSS (skipped while robots.txt disallows it). americansentiment.com and
  prophecygov.com are dropped at every parse point and refused in `PoliteFetcher.allowed`. The YouTube search
  runs only after `require_vpn()` and checks it again before every search.
- Each item's text is kept verbatim: GDELT headline, whole press-release sentences, and a `<mark>` on the
  meeting word only, rendered by `highlightSnippet` (React-escaped, no `dangerouslySetInnerHTML`).
- Host labelling is honest: `host_type = 'company'`, "company meeting, not a government meeting" on every card,
  unconfirmed items counted and not shown, recording candidates labelled "not yet reviewed".
- PK and FK constraints are declared for all three marts (FK `master_org_id → mdm_organization`, `project_id`,
  `jurisdiction_id`, `community_event_id`). The marts appear in the public served list with state filters, in
  the Neon `CIVIC_SERVING` list and its test, and in the ODCS contracts. The issue's dated contract notes are
  matched (`master_org_id`, the `_recording` mart, `GET /api/data-centers/projects`).
- The scope label follows the page's `?state=&city=` scope and moves with the API query in both new sections.
- OpenTelemetry spans on both endpoints and on the frontend fetches; loguru in the loaders.

## Findings
### 🔴 Blocking (Critical)
1. **`dbt_project/models/intermediate/int_data_center_news_item__match.sql:100`: the event date is the first
   date anywhere in the body, so press releases get their dateline as the meeting date.** `regexp_match` returns
   the first month-day in `title — snippet`. A wire-style release opens with "CITY, Oct. 2, 2026 --", and the
   branch's own test fixture is exactly that (`test_community_events.py:145`: "DALLAS, Oct. 2, 2026 -- Applied
   Digital will hold a town hall …"). `verbatim_passages` keeps that sentence because it says "town hall", so the
   event gets `event_date = 2026-10-02` and `event_date_basis = 'stated'`. The card shows that date as when the
   meeting happens. The same happens with any earlier date in the text: "Announced March 3, 2025, … town hall
   Oct. 7" resolves to March 3, 2025. *Verified:* ran the compiled regex read-only in psql on those strings and
   got `Oct/2/2026` and `March/3/2025`. *Fix:* take the date from the sentence that names the meeting word,
   after the word, never from a leading dateline (`^[A-Z .,]+, <date> --`). If that is ambiguous, leave
   `event_date` null ("Date not stated"). Add a dbt unit test with the dateline fixture.

### 🟡 Should fix (Important, non-blocking)
2. **`int_data_center_news_item__match.sql:152-156`: the month-day year only rolls forward.** "Dec. 15" in an
   article published 2027-01-05 resolves to 2027-12-15, because `raw_date < published_on - 60` is false. A past
   December meeting is then dated eleven months in the future, and the endpoint sorts it to the top as the
   newest event. *Fix:* also subtract a year when `raw_date > published_on + ~300 days` (or choose the year that
   puts the date nearest the publication date).
3. **`packages/ingestion/src/ingestion/data_centers/community_events.py:108-115`: when a page has no
   `<article>`/`<main>`, the snippet includes the page's `<title>` and its navigation.** `main_content` then
   returns the whole page, and `strip_html` keeps `<head>`, `<nav>`, `<header>` and `<footer>` text. *Verified:*
   all 5 rows in `bronze.bronze_data_center_news_item` (Applied Digital IR feed, landed today) have snippets
   such as "… Polaris Forge 1 :: Applied Digital Corporation (APLD) Skip to main content Skip to section
   navigation Skip to footer Investor …". The first "sentence" runs until the 600-character cut. That text would
   be served as quoted evidence once an item names a meeting word. *Fix:* in the fallback, drop
   `head|nav|header|footer|aside` elements (and the `<title>`) before splitting. Add a test with a page that has
   no `<article>`.
4. **`community_events.py:302-303`: a robots.txt that answers 5xx is treated as "no robots.txt, everything
   allowed".** `resp.status_code >= 400` covers 5xx, but RFC 9309 says a server error means assume full
   disallow. Only 4xx means unrestricted. *Fix:* `elif 400 <= status < 500 or "html" in ctype: parser = None`,
   and disallow-all on 5xx, as the `HTTPError` branch already does.
5. **`community_events.py:402-407`: one failing release page drops the whole feed.** `fetcher.get(link)` is
   not wrapped, so a timeout or connection error on any release page escapes `fetch_company_feed`. `main` then
   catches it (`:550`) and `continue`s, losing every item already parsed from that feed. *Fix:* catch
   `httpx.HTTPError` around the page fetch, log it, and keep the item with its feed-description snippet.
6. **No tests for the SQL matching, dating and grouping.** The intermediate models have only
   `unique`/`not_null`/`accepted_values`. Nothing exercises the date regex, the year rollover, host and project
   precedence, the status rules, or the undated-to-dated grouping in `int_data_center_community_event__item`.
   Findings 1 and 2 would have been caught. *Fix:* add dbt `unit_tests` (given rows → expected `event_date`,
   `event_date_basis`, `status`, `community_event_id` grouping) for `int_data_center_news_item__match` and
   `int_data_center_community_event__item`.

### 🔵 Nits / suggestions (Minor)
7. **`packages/ingestion/src/ingestion/data_centers/recording_candidates.py:182`: the VPN re-check exits with
   the wrong code.** The `require_vpn()` inside the loop isn't caught, so a VPN drop mid-run ends with a
   traceback and exit 1, not the documented exit 5. It still fails safe (nothing more is searched). Wrap `main`
   with `scrapers.youtube.vpn_guard.exit_if_vpn_off`.
8. **`int_data_center_news_item__match.sql:146`: `event_kind = kinds[1]` is the alphabetically first kind, not
   "the first meeting word named" as the header says.** Because `event_kind` is part of the event key
   (`int_data_center_community_event__item.sql:27`), two articles about one town hall split into two events if
   one of them also says "public meeting". Consider leaving the kind out of the key, or taking the kind by
   position in the text.
9. **`community_events.py:322-350` and `:527`: two problems in GDELT error handling.** `fetch_gdelt` can raise
   `PermissionError` (robots.txt disallows the API path), but `main` catches only `RuntimeError`/`HTTPError`,
   so the whole run crashes. After repeated transport errors, the final `RuntimeError` says "still
   rate-limiting", which names the wrong cause.
10. **`community_events.py:271-272`: redirects skip the checks.** The client follows redirects, so the
    blocked-host and robots.txt checks apply only to the first URL. A release link that redirects to a blocked or
    disallowed host would be fetched. Check `resp.url` (or disable redirects and check each hop).
11. **`dbt_project/models/marts/data_center_community_event_recording.sql:22`: recording candidates can vanish
    without a warning.** The candidates are keyed to `community_event_id = md5(event_key)`. If the event key
    changes (a new source changes the kind or project, or the snippet is updated), the candidates no longer
    match any event, and the inner join drops them silently. Consider a test or log line that counts orphaned
    candidates.
12. **Commit and PR linkage.** The commit body says `Refs #530`. The PR description must say `Closes #532` and
    repeat the issue's Attributes table (epic #530) for the PR conventions check.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partial | Branch `feat/532-…` is right and #532 has dated contract notes; the PR body still has to say `Closes #532` |
| Conventional Commits | Yes | `feat(dc): …` with co-author trailer |
| No fabricated data | Yes, with finding 1 | No invented values; finding 1 serves a real date as the wrong fact |
| New Python in `packages/` | Yes | Both loaders are `python -m ingestion.data_centers.*` CLIs; nothing in `scripts/` |
| dbt for transformations | Yes | Matching, dating, grouping all in dbt; Python only fetches and lands |
| Naming | Yes | `state_code` + `state` on the event mart; no `dim_`/`fact_` |
| Keys | Yes | PK on all three marts; FKs to `mdm_organization`, `data_center_project`, `jurisdictions`, `data_center_community_event` |
| Calendar years | n/a | Dates are `date`, serialized as ISO strings |
| Scope label matches filter | Yes | Both sections render `scope.label` and pass the same `?state=&city=` to the API |
| Match evidence on filtered tiles | Yes | Verbatim source text with `<mark>` via `highlightSnippet`; see finding 3 for what the text may contain |
| Docs | Yes | `web_docs/docs/development/data-center-community-meetings.md` (kebab-case, frontmatter, decisions recorded) |
| Telemetry and logging | Yes | OTel spans on both endpoints and fetches; loguru in loaders |
| Tests | Partial | Python helpers and API covered; SQL logic untested (finding 6) |
| Shared libraries | Yes | `packages/hosting` tests run (Neon list change); ingestion tests run |
| Owner rules (free sources, politeness, VPN, blocked hosts) | Yes, with findings 4 and 10 | GDELT 6 s spacing, descriptive UA, robots.txt per host, Google News skipped, `require_vpn` before every search, blocked hosts never fetched |

## Test Coverage
- **Run locally:**
  - `pytest packages/ingestion/tests/test_community_events.py tests/test_api_data_center_community_events.py packages/hosting/tests`:
    48 passed, 3 skipped.
  - `npx vitest run src/lib/dataCenterJobs.test.ts`: 20 passed.
  - `npx tsc --noEmit`: clean.
  - `dbt compile` on the seven new models: compiles.
  - `ruff check` on the changed Python: clean for the new files; 2 errors in `sync_public_to_neon.py` (`io`
    unused, E731) are on lines this branch didn't touch.
  - The `/projects` mentions SQL (stage regexes) was run read-only against `gold`: valid.
- **Covered:** meeting-word and data-center matching, blocked hosts, GDELT and RSS parsing, verbatim
  sentence splitting, User-Agent, robots disallow and missing robots, GDELT 429 backoff, recording-candidate
  window, `main_content` with an `<article>`, API confirmed-only with sources, missing relation, and timeline
  order and host labels.
- **Not covered:** the dbt date, status and grouping logic (finding 6); robots 5xx; a page without
  `<article>`/`<main>`; feed page errors; the VPN re-check in the loop.
- **Warehouse state (read-only):** bronze holds 5 company-feed items, none naming a meeting word. The
  `gold.data_center_community_event` table is empty. `dbt ls <model>+` wasn't needed: the models are new and
  their only children are in this diff. The #531 tables (`mdm_organization_data_center`,
  `data_center_project*`) are in `gold` but not yet in local `public`, which the loader's `FEEDS_SQL` reads.
  Publish #540 first.

## Verdict
**request-changes.** Fix finding 1 (take the event date from the meeting sentence, never a dateline or an
earlier date) and add a dbt unit test for it. Fixing 2-6 at the same time is strongly recommended: 2 and 3 also
put wrong or junk text in front of readers, and 6 is the test gap that let 1 and 2 through. The nits can follow
as `action-item` issues.

## Resolution (author, 2026-11-17)

1. 🔴 Fixed: the meeting date is read only after the first meeting word, in the same sentence (no `. X` break
   before it); a dateline or an earlier date gives null. Unit test rows n4 (dateline) and n5 cover it.
2. 🟡 Fixed: a month-day year also rolls back a year when it lands more than 300 days after publication.
3. 🟡 Fixed: without `<article>`/`<main>`, the page's head, nav, header and footer are dropped; the bronze rows
   were re-landed with the new code. Test added.
4. 🟡 Fixed: a robots.txt 5xx means disallow (RFC 9309). Test added.
5. 🟡 Fixed: a release-page error keeps the item with the feed's own text. Test added.
6. 🟡 A dbt unit test (`news_item_match_is_deterministic`) was already on the branch; it now also covers 1 and 2.
7. 🔵 Fixed: a VPN drop mid-run stops with exit code 5.
8. 🔵 Fixed: `event_kind` is the first meeting word in the text, not the alphabetical first.
9. 🔵 Fixed: a GDELT robots refusal is caught per query; the give-up message names both causes.
10. 🔵 Fixed: after a redirect, the final URL is checked against robots.txt and the blocked hosts.
11. 🔵 Kept: candidates follow the event key by design (a regrouped event is a new event); documented here.
12. 🔵 The PR body says `Closes #532` and carries the Attributes table.
