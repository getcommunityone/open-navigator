---
pr: 561
branch: feat/525-dc-company-from-meeting
title: "feat(dc): name the company behind a data center decision from the meeting's own words"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: data-dbt-specialist subagent (read-only), verified by the coordinator against the code, a read-only query and the dbt unit tests
verdict: approve-with-nits
---

# PR Review: feat(dc): name the company behind a data center decision from the meeting's own words

## Summary
The PR extends `decision_company_mention` so a company is named from the transcript passages of the decision's own
meeting, not only from its headline and statement. The match is deterministic SQL in dbt, needs a cue that the company
is the applicant or developer, respects the decision's discussion window when the analysis gave one, and keeps a
verbatim quote for every row. It works: 0 → 1 of the 25 question decisions now names a company (2 companies, both with
quotes), and the API and UI show the quote and a link to the recording. The review found one latent defect in the
window (fixed in `66100281`, with a test that fails on the old code) and one nit, both verified. Two further notes
(commit trailer, 5 examples) are below. Verdict: approve with nits.

## Scope of Change
- Files changed: 15 (+698 / -69; 13 files, +657 / -63 without the two generated ODCS contracts)
- Areas touched: dbt_project (model, macro, seed, schema, test, contracts), api, web_app, web_docs
- Commits:
  - `e88b36d3` feat(dc): name the company behind a data center decision from the meeting's own words (#525)
  - `66100281` fix(dc): build the discussion window from every entry of a repeated decision_id (#525)
- Range reviewed: `0ba4fcd2..66100281`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Docker Build Test (Full Stack) | skipping (no Docker files changed; not required) |

Read on head `66100281`.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Pattern scan of the added lines found no key, password, token or credentialed URL; the
  pre-commit secret and private-key hooks passed.
- **Fabricated data in a served path:** clean. No literal figures in `api/` or `web_app/src/`. The two seed rows carry
  a verbatim `source_passage` and a link to the moment, and the model returns no row when no passage has a cue. The
  PR reports the real count (1 decision) instead of padding to 5.
- **Personal data:** clean. Public meeting records only; no user location or address is stored or logged.
- **Destructive or bulky changes:** clean. No `data/cache/` reference, no deletions, no large files. The seed CSV
  changed by 42 lines. The model is built by dbt only.

## Strengths
- The cue rule is narrow on purpose, and the PR lists six near-misses it rejected, so the precision is visible.
- Evidence is checkable: `assert_decision_company_passage_evidence_is_verbatim` fails when a quote is not a
  substring of the passage; `data_center_meeting_mention_id` is a declared FK to the passage it came from.
- The unit test pins each rule separately: cue before, cue after, passing mention, out-of-window passage, untimed
  passage under a window, other meeting, `decision_text` winning.
- Regexes reuse `regex_escape`, so an alias with punctuation cannot break the pattern. Highlighting is rendered by
  `highlightSnippet` (React-escaped), with no `dangerouslySetInnerHTML`.
- The change is honest about what it does not do (#559, #560 filed with the four parts).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Window built from two different entries** (`dbt_project/models/marts/decision_company_mention.sql`, `windows` CTE).
   `max(window_start)` and `max(window_end)` were taken independently, so when one analysis lists a `decision_id`
   twice, the window could use the start of one entry and the end of the other, and drop passages inside an entry's
   own window. Verified in the SQL, and against the warehouse: 36 `(analysis, decision_id)` pairs repeat among 15,607
   decision entries, so the shape occurs, but none of them has differing windows today, so no current row changed.
   **Fixed in `66100281`**: earliest start and latest end across the entries. The new case in
   `company_mention_from_meeting_passage` (windows 100–200 s and 900–1000 s) fails on the old `max()` and passes now.
   The model rebuilt locally gives the same 2 rows for the same 1 decision.

### 🔵 Nits / suggestions (Minor)
1. **`companyMentionLink(m)` called twice** (`web_app/src/pages/PolicyQuestionsPage.tsx`, the company row). Harmless,
   but it made the reader check both calls match. **Fixed in `66100281`** (read once per row).
2. **Commits lack the agent co-author trailer** that the rubric's Conventional Commits row asks for
   (`Co-Authored-By: Claude …`). Both commits are already on a branch with an open PR, so the history is not
   rewritten. The review commit carries the trailer.
3. **"5 examples" in the issue's "Done when" is not met, and the PR says so.** Only one decision has a company named
   by a passage with a cue. This is a limit of the data and the no-guesses rule, not of the code, and the PR shows
   the rejected near-misses. Whoever merges should accept this knowingly; #559 (discussion windows) and #560 (a
   source outside the meeting) are the paths to more.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/525-dc-company-from-meeting`; `Closes #525`; the issue has the four parts; follow-ups #559 and #560 filed |
| Conventional Commits | Yes, with a nit | Both subjects conform; trailer missing (nit 2) |
| No fabricated data | Yes | Scan above; empty state when no passage qualifies |
| New Python in `packages/` | Yes | No new `scripts/` file; the API edit extends an existing route |
| dbt for transformations | Yes | All matching is SQL in a mart model and macros; none in Python |
| Naming | Yes | `state_code` and `state` unaffected; no `dim_`/`fact_` names |
| Keys | Yes | PK `decision_company_mention_id`; FKs to `event_decision` and `data_center_meeting_mention`; contract enforced |
| Calendar years | n/a | `start_seconds` is a time offset, not a year |
| Scope label matches filter | n/a | No scope or filter surface changed |
| Match evidence on filtered tiles | Yes | The quote is verbatim and `<mark>`ed; rendered by `highlightSnippet` |
| Docs | Yes | Extends `web_docs/docs/development/decision-place-and-company.md`; no new root `.md` |
| Telemetry and logging | n/a | No new span or logger; the route's existing instrumentation applies |
| Tests | Yes | New dbt unit test and singular test, 3 API tests, 4 UI helper tests; the window fix has a regression case |
| Shared libraries | n/a | Nothing under `packages/` changed |

## Test Coverage
- **dbt** (local warehouse, `localhost:5433`): `decision_company_mention`, the seed and the verbatim test, 28 passed
  after the fix; both unit tests pass. The new duplicate-window case fails on the old SQL (checked by restoring
  `max(window_start)` temporarily) and passes on the fix. `dbt ls --select decision_company_mention+` showed no
  downstream dbt model.
- **ODCS:** `python -m models.odcs --check` passes (no column changed in the fix).
- **API:** `pytest tests/test_api_policy_questions.py` 24 passed; `ruff check` clean.
- **Frontend** (clean copy, because `web_app/node_modules/.bin` is root-owned here): `tsc --noEmit` clean, `eslint` clean on
  the changed files, `vitest` 72 passed.
- **Not covered:** a browser check of the dashboard row; the real-data effect of the window rule, since no data center
  decision has a `media_anchor` yet (#559).

## Verdict
Approve with nits. Nothing blocks the merge: the one defect found is fixed and tested, and the checks are green. Before
merging, accept the 1-of-5 example outcome (nit 3). The merge itself is the owner's call; this review did not merge or
comment on the PR.
