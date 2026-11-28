---
pr: 1464
branch: feat/1399-trending-terms
title: "feat(trends): trending terms and hot words from meeting speech"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: general-purpose review subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(trends): trending terms and hot words from meeting speech

## Summary
This PR adds trending-term and hot-word detection from meeting speech. It is free and deterministic: dbt/SQL marts,
a small FastAPI route, and a chip row on Browse all topics. It works end to end on the local warehouse: the marts
build, the API serves ranked terms with highlighted evidence, and Playwright passes at Pixel 7 and 1440. A read-only
reviewer found 8 issues. 6 were verified and fixed here. 2 were filed as follow-ups (#1468, #1469); they extend
patterns that already exist in the codebase. The verdict is approve-with-nits.

## Scope of Change
- Files changed: 34 (+3,427 / -2), including generated ODCS contracts and this review.
- Areas touched: api, web_app, web_docs, dbt_project, packages/hosting (Neon sync list only), tests.
- Commits: Conventional feat/test/docs/perf/fix/chore commits on `feat/1399-trending-terms`, each with the co-author
  trailer; two merges of origin/main; two bot review commits.
- Range reviewed: `merge-base(origin/main)..HEAD`.

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass (210e9330) |
| Documentation Build | pass |
| Backend Tests | pass (210e9330). An earlier run failed on missing ODCS contracts; they were regenerated. |
| API Types | pass |
| PR conventions | pass |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every number traces to `trending_term`, and every quote to a transcript. Test fixtures are
  labelled and stay in tests.
- Personal data:
  - Private names are filtered out of terms (`person_name`): 1,185 otherwise-eligible candidates were dropped.
  - Sensitive terms never carry a speaker (enforced in the mart and the API).
  - Self-introductions are redacted.
  - School boards and possible minors are excluded, including through the transcript fallback (fixed after review).
- Destructive data changes: none. New tables only; no Neon writes.

## Strengths
- Presence is read the same way for every meeting, from the transcript vector. Turn coverage doubled in 2026, and
  mixing turn text with transcripts would have made shares move with that coverage.
- The denominator equals `recorded_meeting_year` row for row, and a test checks it.
- The build is memory-safe: the candidate sample is tokenized one meeting at a time in a LATERAL, only rolled-up
  counts are stored, and `work_mem` and a statement timeout are set.
- Serving stays under budget: about 2.9 MB (terms 1.2 MB + evidence 1.7 MB).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. `TrendingTermsRow.tsx` / `api/trendingTerms.ts`: the city note disappeared once data loaded, because `city` was
   never sent. **Fixed**: the label comes from the URL's city, and `city` is sent and part of the query key. The test
   no longer pre-fills `requested_city`.
2. `trending_term_evidence.sql`: a possible minor's words could be quoted through the transcript fallback. **Fixed**:
   the `minor_hit` CTE skips any (term, meeting) where a possible-minor segment says the term.
3. `trending_term_evidence.sql`: substring `strpos` could land on "rent" inside "parent", leaving an excerpt without
   the term. **Fixed**: a whole-word regex picks the window, rows without `<mark>` are dropped, and a data test checks
   the excerpt.
4. `int_trending_term__candidate.sql`: the sensitive flag checked only the display form. **Fixed**: it also matches the
   stemmed key ("homelessness", plurals).
5. Full private names can appear in transcript excerpts (the chair calling a speaker by name). This is the same exposure
   as the existing `/search` snippets. **Filed** as #1468 (action-item).

### 🔵 Nits / suggestions (Minor)
6. The official-name exception isn't tied to a state. **Filed** as #1469.
7. Evidence `total_meetings` returned 0 when the scope row isn't published. **Fixed**: it now returns null (tested).
8. The public evidence table had no key column. **Fixed**: `trending_term_evidence_id` is served.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1399 has all four parts; branch `feat/1399-...`; `Closes #1399`; follow-ups #1468 and #1469 |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | No Python transformations; only an API route and tests |
| dbt for transformations | Yes | |
| Naming | Yes | `state_code` and `state` on the mart; no dim_/fact_ names |
| Keys | Yes | Both marts have a PK; evidence has an FK to the term's national row |
| Calendar years | Yes | Integer in storage, string on the wire |
| Scope label matches filter | Yes | `?state=` drives the label and the query; a city is answered for its state, and the page says so |
| Match evidence | Yes | `ts_headline` -> `highlightSnippet`; no dangerouslySetInnerHTML |
| Docs | Yes | `web_docs/docs/development/trending-terms-and-hot-words.md` |
| Telemetry | Yes | OpenTelemetry spans on both routes |
| Tests | Yes | See below |

## Test Coverage
- pytest `tests/test_trending_terms.py` (12 tests), run locally against the warehouse:
  - API shapes and SQL safety.
  - The meeting base equals `recorded_meeting_year`.
  - A served term's counts equal a direct full-text recount.
  - The privacy filter drops a sample private first name ("john"), and no served single word is a given name.
  - Boilerplate is excluded.
  - Sensitive evidence has no speaker.
  - Serving stays at 3 MB or less.
- vitest: the trends helpers and the chip row (8 tests). `tsc --noEmit` and eslint are clean.
- Playwright `web_app/e2e/trending-terms.check.mjs`: Pixel 7 and 1440, national and GA. All checks pass.
- `ruff check` is clean on the new Python. `python -m models.odcs --check` and the datamodels tests pass.

## Verdict
approve-with-nits. Merge once required CI is green on the head commit.
