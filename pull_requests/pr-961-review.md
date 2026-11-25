---
pr: 961
branch: feat/955-dc-hearing-leads
title: "feat(data-centers): show upcoming data center hearings only once the government's own page confirms them"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only) and coordinator
head_sha: aa5de7c9
verdict: approve-with-nits
---

# PR Review: feat(data-centers): show upcoming data center hearings only once the government's own page confirms them

## Summary

This PR turns research leads on upcoming data center hearings into hearings the site shows, but only after the
government's own page confirms them. It adds a lead seed, a polite fetch CLI, verification in dbt, a verified-only
served slice, an API, and a "Hearings coming up" section on `/data-centers`.

The first review found that verification only required the date and a data center word to appear *anywhere* on the
page, so topic pages verified on stray dates, and "December 1, 2025" matched a 2026 lead. That, and every other
finding, is fixed in `58b8c390` and covered by a dbt unit test. Five hearings verify on the local warehouse, two of them
flagged **Tentative**. Verdict: **approve-with-nits**. The nits are the substring city filter (#946, site-wide) and the
missed date formats below.

## Scope of Change

- Areas touched: dbt_project (seed, source, 2 marts, unit test, serving macro, contracts), packages (ingestion CLI and
  tests, hosting Neon list), api (route and tests), web_app (types, page section), web_docs (2 pages)
- Commits: b814046f (feature), 58b8c390 (review fixes), plus CI bot review commits
- Range reviewed: `origin/main...aa5de7c9`

## CI Status

| Check | Status |
|---|---|
| Required checks | see PR checks on the head |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. The loader reads the DSN from the environment and never prints it.
- Fabricated data: clean.
  - Leads are never served; only `data_center_hearing_verified` is published.
  - Each served row quotes the official page verbatim.
  - The lead's own body and topic are labelled "From the research lead".
- Personal data: none (public meeting notices).
- Destructive: none. A new bronze table, which the loader creates if it doesn't exist.

## Strengths

- Leads and facts are kept apart all the way through: research leads stay in `gold`, and only verified rows are
  published. Every gap has a status, and blocked or refused sources fail closed.
- The fetcher reuses the existing polite fetcher (robots.txt, `BLOCKED_HOSTS`, spacing, a redirect re-check) and never
  falls back to the production DSN.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

All fixed in `58b8c390`:

1. **The date and the data center word could be anywhere on the page.** **Fixed:** a web page needs the word within
   ~500 characters of a statement of the date (PDF agendas anywhere, since the agenda is the meeting). A written date
   followed by a different year no longer matches, and written dates are case-sensitive. New status
   `date_not_with_item`. The unit test covers "December 10", "December 1, 2025", far apart, a PDF agenda, tentative,
   lowercase prose, and tracker-only.
2. **The " … " evidence joined the date to the site menu.** **Fixed:** the evidence is the date's own passage, plus the
   nearest data center passage *of the same section* (or agenda), trimmed to whole words.
3. **`HighlightAll` marked a lone "Center".** **Fixed:** whole phrases are marked with the site regex.
4. **Unverified parts of the lead were shown as confirmed.** **Fixed:** the copy now says "listed on the government's
   page … Dates can change". The **Tentative** flag shows on tentative, expected, not final or TBD. The lead's topic and
   body are labelled as the research lead's.
5. **No tests of the verification logic.** **Fixed:** dbt unit test `dc_hearing_verification_rules`, 8 cases.

### 🔵 Nits / suggestions (Minor)

- **Fixed:**
  - partial words at the evidence edges are trimmed;
  - a scanned PDF records "PDF has no text layer (scanned?)";
  - page text is capped at 1,000,000 characters;
  - `clean_url` leaves URLs without tracking parameters untouched (tested);
  - unverified leads are no longer published to `public` or Neon.
- **Open:**
  - The city filter is a substring match. It's the same on every data center route, tracked site-wide in #946.
  - Still unmatched: numeric dates without a year ("12/1"), day-first ("1 December 2026") and "Dec.1". The rule fails
    closed on these: a lead reads `date_not_found` rather than verifying wrongly.
  - The heading count is the whole-scope count while items cap at 100, which is harmless at today's volume.
  - The section is hidden when nothing is verified in scope, as documented. "On the agenda" below still covers the
    place.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/955-…`; `Closes #955`; four parts |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | only verified, quoted, linked rows are served |
| New Python in `packages/` | ✅ | `python -m ingestion.data_centers.fetch_hearing_sources` |
| dbt for transformations | ✅ | verification, evidence and status are all dbt; Python only fetches |
| Naming | ✅ | `state_code` + `state` |
| Keys | ✅ | PKs and FKs on both marts; the left-out FK to the gold-only table is documented in `data-contracts.md` |
| Scope label matches filter | ✅ (see #946) | same `?state=&city=` handling as the rest of `/data-centers` |
| Match evidence on filtered tiles | ✅ | verbatim official text, whole phrases marked, React-escaped |
| Docs | ✅ | `development/data-center-hearings.md`, `development/data-contracts.md` |
| Telemetry and logging | ✅ | OTel span on the route; loguru in the CLI |
| Tests | ✅ | dbt unit test (8 cases), API (6), loader (5) |

## Test Coverage

- Local warehouse: a live fetch of the 11 official URLs, then dbt. 5 verified, each read by hand:
  - Harpersville AL, Nov 30;
  - Deer Park TX, Dec 1;
  - Lebanon Twp NJ, Dec 1;
  - Pima County AZ, Dec 8 (tentative);
  - Savannah GA, Dec 15 (tentative).

  The rest: Cochise `date_not_with_item`; Wichita and Larimer disallowed by robots.txt; Forward Pinellas 403;
  Brownfield a scanned PDF; Shawnee no mention.
- `dbt test`: 21/21 including the unit test. pytest: 110 + 84 passed across the touched packages. vitest: 379 passed.
  `tsc` and eslint clean. Docs build OK. `models.odcs --check` current.
- In a real browser (branch router on a spare port, Vite pointed at it): 6 cards nationally and 2 for `?state=AZ`
  before the review fixes. The page logic is unchanged apart from the copy, badge and labels.

## Verdict

**approve-with-nits**: merge when the required checks are green.
