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
decision's own meeting (same `video_id`, discussion window when the analysis gave one, and a cue that
the company is the applicant or developer), not only from its headline or statement. Matching stays in
dbt; every row keeps a verbatim `<mark>`ed quote; the API and UI label meeting hits **"Named in the
meeting"** and link to the recording. Local warehouse matches the PR: 2 `meeting_passage` rows
(Hillwood, PowerHouse Data Centers) on the Spalding FLUME decision (`LGJDZSrSoBU` at 2082.079 s) —
0 → 1 of the 25 question decisions. CI required checks that finished on the prior head were green;
Backend Tests / API Types were still running when this review was written. One Important latent defect
remains in the repeated-`decision_id` window collapse. Verdict: approve with nits.

## Scope of Change
- Files changed: 15 (+698 / -69 on the feature/fix commits; ODCS contracts +40/−6; review file separate)
- Areas touched: dbt_project (model, macro, seed, schema, singular test, contracts), api, web_app, web_docs
- Commits:
  - `e88b36d3` feat(dc): name the company behind a data center decision from the meeting's own words (#525)
  - `66100281` fix(dc): build the discussion window from every entry of a repeated decision_id (#525)
  - `e4080b5a` docs(review): add the review of PR 561 (#525)
  - prior `docs(review): PR #561 review` on the branch (overwritten by this file)
- Range reviewed: `0ba4fcd2..HEAD` (base is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass (on `1e16355d`) |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | in progress at review time (prior head `e4080b5a` had pass) |
| API Types (OpenAPI -> TypeScript) | in progress at review time (prior head `e4080b5a` had pass) |
| PR conventions (linked issue) | pass |
| Docker Build Test (Full Stack) | skipped (no Docker files; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. Full-diff pattern scan found no keys, passwords, tokens or credentialed URLs.
- **Fabricated data in a served path:** clean. No literal dollar amounts or placeholder figures in `api/`
  or `web_app/src/`. Seed `source_passage` values are verbatim meeting words with links; empty state when
  no cue matches. The PR reports the real count (1 decision, 2 companies) instead of padding to 5.
- **Personal data:** clean. Public meeting records only; no user location or address stored or logged.
- **Destructive or bulky data changes:** clean. No `data/cache/` touch, no large dumps, no warehouse
  writes outside dbt. Seed CSV changed by 42 lines.

## Strengths
- Cue rule is narrow on purpose; the PR lists rejected near-misses so the precision is visible.
- Evidence is checkable: singular test `assert_decision_company_passage_evidence_is_verbatim`; FK
  `data_center_meeting_mention_id` → the passage; UI uses `highlightSnippet` (no `dangerouslySetInnerHTML`).
- Unit test `company_mention_from_meeting_passage` pins cue-before, cue-after, no-cue, out-of-window,
  untimed-under-window, other-meeting, `decision_text` winning, and the duplicate-window regression (p6).
- Follow-ups #559 and #560 are filed; the PR is honest that only one decision qualifies today.
- New API tests fail when `policy_questions.py` is reverted to `main` (confirmed locally), then pass on restore.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`decision_company_mention.sql` `windows` CTE: collapsing repeated `decision_id` entries into
   `min(window_start), max(window_end)` fills the gap between non-contiguous windows.** `66100281`
   correctly stops pairing one entry's start with another's end, and the p6 unit case (100–200 s and
   900–1000 s) needs both ends. But a passage whose 3-minute slice sits only in the gap (e.g. index 2 →
   [360, 540]) overlaps neither entry and still matches the span. *Verified:* read-only SQL simulation of
   that shape: span hits `early|gap|late`; any-entry overlap hits only `early|late`. Warehouse today:
   27 repeated `(analysis_id, decision_id)` pairs, **0** with differing non-null windows, so no current
   row is wrong; **0** of 35 data-center decisions have a `media_anchor`. *Fix:* keep one row per entry
   in `windows` and let `decision_passages` count when **any** entry overlaps (or when there is no
   window). Extend the unit test with a gap passage that must not match — especially before #559 lands
   real windows.

### 🔵 Nits / suggestions (Minor)
2. **When both cue-before and cue-after match the same company in one passage, `chosen` has no
   tie-break**, so which `<mark>`ed excerpt is served can flip across rebuilds. *Verified:* the live
   PowerHouse passage matches both `teamed up with Powerhouse` and `Powerhouse is a … developer`; the
   served row currently uses cue-before. Prefer earlier `strpos` (or cue-before) in the `ORDER BY`.
3. **Issue "Done when" asked for 5 examples; the PR delivers 1 and says so.** Limit of the data under
   the no-guesses cue rule, not a code defect. Accept knowingly on merge; #559 / #560 are the paths to more.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/525-dc-company-from-meeting`; `Closes #525`; issue has Problem / Done when / Contract / Read first; follow-ups #559, #560 |
| Conventional Commits | Yes | `feat(dc):` / `fix(dc):` / `docs(review):`; Cursor co-author trailers on the commits |
| No fabricated data | Yes | Scan above; real warehouse counts |
| New Python in `packages/` | Yes | No new `scripts/`; API extends an existing route |
| dbt for transformations | Yes | Matching in the mart + macros; Python only serves |
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
  - `pytest tests/test_api_policy_questions.py` with worktree `PYTHONPATH`: **24 passed**. Reverting
    `api/routes/policy_questions.py` to `main` fails the 3 new tests; restore passes.
  - `ruff check` on touched Python: clean.
  - `npx tsc --noEmit -p web_app`: clean aside from expected missing-`vitest` errors in `*.test.ts`.
  - `dbt ls --select decision_company_mention+` and `dbt compile --select decision_company_mention`:
    succeed (deps symlinked read-only from the main checkout). No downstream dbt model. **`dbt test` /
    `dbt run` not run** (local rebuild holds tables; rubric forbids writes).
  - Read-only warehouse (`localhost:5433` / `open_navigator`): new columns present; **2** rows, both
    `meeting_passage`, both with `<mark>` in `evidence`, `start_seconds = 2082.079`, video
    `LGJDZSrSoBU`, headline "Data Center Campus FLUME Amendment Denied"; **1** of **25** question
    local decisions (`policy_question.decisions_total = 25`); **35** data-center decisions overall;
    **0** repeated decision entries with differing windows; **0** DC decisions with `media_anchor`.
- **PR claims left unverified here:** `dbt test` "28 passed", `python -m models.odcs --check`,
  vitest/eslint/frontend and docs builds (CI Frontend/Docs green as a proxy on the prior review head).
- **Covered in-repo:** cue/window/same-meeting rules (unit test), verbatim quote singular test, API
  `jump_url` / untimed link / SQL join, UI label and link helpers.
- **Not covered:** gap passage under a span window (finding 1); cue tie-break (finding 2); browser
  render of the dashboard row.

## Verdict
**approve-with-nits.** Nothing blocks merge for today's data. Before or soon after merge — and before
#559 adds real `media_anchor` windows — fix finding 1 so repeated `decision_id` windows mean "overlaps
any entry", not "overlaps the bounding span", and add the gap unit-test case. Finding 2 is a small
determinism tidy-up. Accept the 1-of-5 example outcome knowingly. This review was not posted to GitHub
as a comment or approval.
