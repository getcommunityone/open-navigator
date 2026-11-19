---
pr: 584
branch: fix/444-hardcoded-stats
title: "fix(web_app): read card counts from /api/stats and drop typed-in figures"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(web_app): read card counts from /api/stats and drop typed-in figures

## Summary
The PR removes the typed-in counts named in #444. The Explore cards now read `events`, `bills`, `nonprofits` and `leaders`
from the national `GET /api/stats` rollup through a new `useNationalStats()` hook and `formatLiveStat()`. A missing,
zero or non-numeric count hides the chip, so no stand-in number is shown. The Analytics page loses three typed-in cards
(15,000+, +3.2%, 50). The nav flyout strings, the `index.html` meta tags and the docs homepage no longer make numeric
claims. The change does what the issue asks, matches "No Fabricated Data", and CI is green on the head commit. I
verified the four rollup fields exist and hold real values in the local warehouse. One non-blocking gap remains: the same
"1.8M nonprofits" claim survives in the docs site's `StructuredData.tsx`. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 9 (+103 / -82; no generated files in the diff)
- Areas touched: web_app, web_docs
- Commits:
  - `52ca9bdb` fix(web_app): read card counts from /api/stats and drop typed-in figures
- Range reviewed: `0ba4fcd2..52ca9bdb` (merge base of `origin/main` and `fix/444-hardcoded-stats`; the base branch is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | SUCCESS (the job runs `tsc --noEmit`, `npm test` and `npm run build`, so the new vitest file ran in CI) |
| Documentation Build (Docusaurus) | SUCCESS |
| Backend Tests (Python) | SUCCESS |
| API Types (OpenAPI -> TypeScript) | SUCCESS |
| PR conventions (linked issue) | SUCCESS |
| Detect Docker-relevant changes | SUCCESS |
| Docker Build Test (Full Stack) | SKIPPED (not required; no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The diff holds no keys, tokens, credentialed URLs or cookies.
- **Fabricated data in a served path:** clean, and the PR removes the existing violations. `formatLiveStat` returns `null`
  unless the value is a finite number above zero, and `ActionCard` renders no chip for `null`. The only literals added
  are the non-numeric caption "Federal, state & foundation" and the nav strings "Organizations mapped by issue and
  location", "Officials" and "Funding". None is a number. The `13,456` in the test is a fixture inside a test file.
- **Personal data:** clean. Only national aggregate counts are read; nothing is stored or logged.
- **Destructive or bulky data changes:** clean. 103 lines added, nothing under `data/`, no warehouse writes.

## Strengths
- **No fallback figure anywhere.** The helper's contract is "number or nothing", and `liveStats.ts` and its test say so.
- **One shared request.** `useNationalStats` uses the `['national-stats']` key that Home and Analytics already used.
  `ActionCard` calls it once per card, but every card subscribes to the same cache entry.
- **The wiring is typed.** `NationalStatKey` limits `liveStat.key` to fields the API returns, so a typo is a compile error.
- **The PR is candid about what it couldn't run.** The body says the test file and the rendered cards were not run
  locally. CI now covers the test (the `npm test` step passed).
- **A follow-up was filed** for the out-of-scope files ([#583](https://github.com/getcommunityone/open-navigator/issues/583)).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`web_docs/src/components/StructuredData.tsx:15`, `:70`, `:74`: the "1.8M nonprofits" claim is still served on the
   docs site.** The three strings are JSON-LD for search engines ("Track local governments, 1.8M nonprofits, …" and
   "Monitor 1.8M nonprofits"). This is the same figure the PR removes from `web_app/index.html`. #444's file list did
   not name this file, so the PR body's "no `N+` count left in the files named in #444" is true, but the claim
   survives in the docs site's SEO metadata. *Verified:* `rg "1\.8M|3M\+|13,000\+|1,000\+" web_docs/src web_app/index.html`
   on the head commit finds only these three lines. They are not in #583's scope either (#583 names `AdvocacyTopics.tsx`
   and `NonprofitsHF.tsx`). *Fix:* drop the figure from those three strings in this PR, or open an `action-item`
   issue for it and link it from the PR.

### 🔵 Nits / suggestions (Minor)
2. **`web_app/src/pages/Analytics.tsx:195`: "across all 50 states" is still typed in.** The PR removed the "States
   Covered 50" card, but the "Budget Data Integration In Progress" notice says budget data is being integrated "across
   all 50 states". It describes intent, not a count, so it isn't a fabricated figure. Since the notice sits beside
   the card the PR deleted for the same claim, consider rewording it ("across the jurisdictions we cover").
3. **`web_app/src/pages/Home.tsx:381`: Home still defines its own `['national-stats']` query.** Home's `queryFn` and
   `staleTime` duplicate the new hook, whose docstring says Home shares it (it shares only the query key). If the two ever diverge, the
   cache entry flips between shapes. Home types the data as `LocationStats`, so it needs a small type change to use
   `useNationalStats`. Not required for this issue; a follow-up cleanup.
4. **Nothing stops a number being typed into `ExploreCard.stats` again.** `liveStats.test.ts` covers the helper but not
   the card data. A small test over the exported card lists asserting that `stats` contains no `\d{2,}` would keep the
   regression out. Existing `stats: '48-hour impact'` (Hackathons) is a duration, not a count, and would need an
   allowlist entry.
5. **Chip wording and provenance.** The Policy Decisions card now says "153,235 meetings" (the live national `events`
   figure). `events_count` is `COUNT(*)` over `bronze.bronze_events_localview`
   (`jurisdiction_state_aggregate.sql:135`), a single source, so "meetings" in the whole catalog may be higher. The
   number is real and the same figure Home shows, so this isn't a data error. A noun such as "meetings tracked" would
   avoid reading as a national total. Also, the issue's "Done when" says "—" when unavailable; the PR hides the
   chip instead, which fits "No Fabricated Data" better, so I'd accept it as-is.
6. **`web_docs/src/pages/index.tsx:323`, `:330`, `:337`: the emoji stand-ins have no `aria-hidden`.** Screen readers
   will read "office building" before "Nonprofit Organizations". Add `aria-hidden="true"` to the three `<div>`s.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/444-hardcoded-stats`; body says `Closes #444`; #444 has Problem, Done when, Contract, Read first; follow-up #583 filed |
| Conventional Commits | Yes | `fix(web_app): …` with the Cursor co-author trailer |
| No fabricated data | Yes, with finding 1 | Every shown count is read live or hidden; one stale claim in docs metadata |
| New Python in `packages/` | n/a | No Python changed |
| dbt for transformations | n/a | No dbt changed |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | Explore cards are national, unfiltered; no scope control exists on them |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | No new docs files |
| Telemetry and logging | n/a | No FastAPI or script changes. The hook adds no new tracing; the request already goes through the shared `api` client |
| Tests | Mostly | Helper has a test that would fail without it; card wiring untested (finding 4) |
| Shared libraries | n/a | |

## Test Coverage
- **Run locally:**
  - `cd web_app && npx tsc --noEmit -p .`: no errors outside `*.test.ts`. The only errors are the expected vitest
    ones, in `src/lib/timestamp.test.ts`.
  - A Node TypeScript-stripping run of `formatLiveStat`: `{bills: 13456}` gives "13,456 bills"; a zero count and a
    missing field both give `null`. This matches the test's expectations. I did not run vitest (not installed here).
  - CI's `npm test` step on the head commit passed, so `liveStats.test.ts` ran there.
- **Read-only warehouse check** (`public.jurisdiction_state_aggregate`, `level = 'national'`, updated 2026-11-17):
  `events_count` 153,235; `bills_count` 10,275; `nonprofits_count` 1,926,908; `leaders_count` 34,322. All four fields the
  cards read exist and are non-zero, so the chips will render with the API up. `public.contact_official` has 34,322
  rows, matching `leaders_count`, so "officials" is the right noun. The API maps these columns to `events`, `bills`,
  `nonprofits` and `leaders` in `api/routes/stats_neon.py` (lines 405-413). When no row exists, the fallback returns 0,
  which the helper hides.
- **Covered:** real count formatting; null, undefined, `{}`, null field, zero and NaN each give no chip; the spec
  reads only its own key.
- **Not covered:** `ActionCard` rendering with and without stats, and that no typed-in number returns (finding 4).
  The PR body says it did not see the rendered cards; I did not either (no browser run), so "chips show real counts
  with the API up and none with it down" is traced in code and the warehouse, not seen on screen.
- **Unverified claim in the PR body:** "`vite build` could not run locally". CI's Frontend Build ran it and passed.

## Verdict
**approve-with-nits.** Nothing blocks the merge. Please remove the "1.8M nonprofits" strings from
`web_docs/src/components/StructuredData.tsx` (finding 1) or log them as an `action-item` issue linked from the PR. The
nits can follow as small issues or be folded into #583.
