---
pr: 561
branch: feat/525-dc-company-from-meeting
title: "feat(dc): name the company behind a data center decision from the meeting's own words"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(dc): name the company behind a data center decision from the meeting's own words

## Summary
The PR extends `decision_company_mention` so a company can be named from a transcript passage of the
decision's own meeting, not only from its headline or statement. Matching stays in dbt (cue that the
company is the applicant or developer, same `video_id`, discussion window when present), every row keeps
a verbatim `<mark>`ed quote, and the API/UI label meeting hits **"Named in the meeting"** with a recording
link. Local warehouse state matches the PR: 2 `meeting_passage` rows (Hillwood, PowerHouse Data Centers)
on the Spalding FLUME decision (`LGJDZSrSoBU`), 0 → 1 of the 25 question decisions. CI is green. One
Important finding remains: the repeated-`decision_id` window fix uses a bounding span, so a passage in the
gap between two non-contiguous windows would count incorrectly. No such differing windows exist in the
warehouse today. Verdict: approve with nits.

## Scope of Change
- Files changed: 15 (+698 / -69; 13 files, +657 / -63 excluding the two generated ODCS contracts); plus this review file
- Areas touched: dbt_project (model, macro, seed, schema, singular test, contracts), api, web_app, web_docs
- Commits:
  - `e88b36d3` feat(dc): name the company behind a data center decision from the meeting's own words (#525)
  - `66100281` fix(dc): build the discussion window from every entry of a repeated decision_id (#525)
  - `e4080b5a` docs(review): add the review of PR 561 (#525)
- Range reviewed: `0ba4fcd2..e4080b5a` (base is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Docker Build Test (Full Stack) | skipped (no Docker files; not required) |

Read on head `e4080b5a` (required checks all SUCCESS).

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Full-diff pattern scan found no keys, passwords, tokens or credentialed URLs.
- **Fabricated data in a served path:** clean. No literal dollar amounts or placeholder figures in `api/` or
  `web_app/src/`. Seed `source_passage` values are verbatim meeting words with links; empty state when no
  cue matches. The PR reports the real count (1 decision, 2 companies) instead of padding to 5.
- **Personal data:** clean. Public meeting records only; no user location or address stored or logged.
- **Destructive or bulky data changes:** clean. No `data/cache/` touch, no large dumps, no warehouse writes
  outside dbt. Seed CSV changed by 42 lines.

## Strengths
- Cue rule is narrow on purpose; the PR lists rejected near-misses so the precision is visible.
- Evidence is checkable: singular test `assert_decision_company_passage_evidence_is_verbatim`; FK
  `data_center_meeting_mention_id` → the passage; UI uses `highlightSnippet` (no `dangerouslySetInnerHTML`).
- Unit test `company_mention_from_meeting_passage` pins cue-before, cue-after, no-cue, out-of-window,
  untimed-under-window, other-meeting, and `decision_text` winning.
- `66100281` correctly stops pairing one entry's start with another's end via independent `max()` bounds;
  the new p6 case would fail on the old SQL.
- Follow-ups #559 and #560 are filed; the PR is honest that only one decision qualifies today.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`decision_company_mention.sql` `windows` CTE: a bounding span over repeated `decision_id` entries
   includes the gap between non-contiguous windows.** `66100281` changed `max(window_start), max(window_end)`
   to `min(window_start), max(window_end)`. That fixes cross-pairing and makes both of the unit-test windows
   (100–200 s and 900–1000 s) count, but a passage whose 3-minute slice sits only in the gap (e.g. index 2 →
   [360, 540]) overlaps neither entry and would still match the span. *Verified:* read-only SQL simulation of
   the unit-test shape: span hits `early|gap|late`; any-entry overlap hits only `early|late`. Warehouse today:
   27 repeated `(analysis_id, decision_id)` pairs among analyses, **0** with differing non-null windows, so no
   current row is wrong. *Fix:* keep one row per entry in `windows` (no collapse), and let
   `decision_passages` count when **any** entry's window overlaps (or when the decision has no window rows).
   Extend the unit test with a gap passage that must not match.

### 🔵 Nits / suggestions (Minor)
2. **Issue "Done when" asked for 5 examples; the PR delivers 1 and says so.** That is a limit of the data under
   the no-guesses cue rule, not a code defect. Accept knowingly on merge; #559 / #560 are the paths to more.
3. **No browser check of the dashboard row** (PR Verification says so). API and helper tests cover the contract;
   a quick look at the Spalding instance would still help before merge.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/525-dc-company-from-meeting`; `Closes #525`; issue has Problem / Done when / Contract / Read first; follow-ups #559, #560 |
| Conventional Commits | Yes | `feat(dc):` / `fix(dc):` / `docs(review):`; Cursor co-author trailers on the commits |
| No fabricated data | Yes | Scan above; real warehouse counts |
| New Python in `packages/` | Yes | No new `scripts/`; API extends an existing route |
| dbt for transformations | Yes | Matching and dating in the mart + macros; Python only serves |
| Naming | Yes | No `dim_`/`fact_`; geo naming untouched |
| Keys | Yes | PK `decision_company_mention_id`; FKs to `mdm_organization` and `data_center_meeting_mention`; relationships test to `event_decision` |
| Calendar years | n/a | `start_seconds` is a media offset |
| Scope label matches filter | n/a | No scope surface changed |
| Match evidence on filtered tiles | Yes | Verbatim quote with `<mark>` via `highlightSnippet` |
| Docs | Yes | Extends `web_docs/docs/development/decision-place-and-company.md` |
| Telemetry and logging | n/a | Existing route instrumentation; no new spans required |
| Tests | Yes, with finding 1 | Unit + singular + API + UI helpers; gap case for repeated windows not covered |
| Shared libraries | n/a | Nothing under `packages/` changed |

## Test Coverage
- **Run locally (this review):**
  - `pytest tests/test_api_policy_questions.py` with worktree `PYTHONPATH`: **24 passed**.
  - `ruff check` on touched Python: clean.
  - `npx tsc --noEmit -p web_app`: clean aside from expected missing-`vitest` errors in `*.test.ts`.
  - `dbt ls --select decision_company_mention+` and `dbt compile --select decision_company_mention`: succeed
    (deps symlinked read-only from the main checkout). No downstream dbt model; tests and the two unit tests
    appear in `ls`. **`dbt test` / `dbt run` not run** (local rebuild holds tables; rubric forbids writes).
  - Read-only warehouse (`localhost:5433` / `open_navigator`): table has the new columns; **2** rows, both
    `meeting_passage`, both with `<mark>` in `evidence`, `start_seconds = 2082.079`, video `LGJDZSrSoBU`,
    headline "Data Center Campus FLUME Amendment Denied"; **1** of **25** question local decisions; **35**
    data-center decisions overall; **0** repeated decision entries with differing windows.
- **PR claims left unverified here:** `dbt test` "28 passed", `python -m models.odcs --check`, vitest/eslint/
  frontend and docs builds (CI Frontend/Docs/API Types are green as a proxy).
- **Covered in-repo:** cue/window/same-meeting rules (unit test), verbatim quote singular test, API
  `jump_url` / untimed link / SQL join, UI label and link helpers.
- **Not covered:** gap passage under a span window (finding 1); browser render of the dashboard row.

## Verdict
**approve-with-nits.** Nothing blocks merge for today's data. Before or soon after merge, fix finding 1 so
repeated `decision_id` windows mean "overlaps any entry", not "overlaps the bounding span", and add the gap
unit-test case—especially ahead of #559, which will introduce real `media_anchor` windows. Accept the 1-of-5
example outcome knowingly. This review was not posted to GitHub as a comment or approval.
