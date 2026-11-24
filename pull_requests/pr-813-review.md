---
pr: 813
branch: feat/807-public-comment-stance
title: "feat(llm): extract public-comment stance in the full and light analysis prompts"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: data-dbt-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(llm): extract public-comment stance in the full and light analysis prompts

## Summary
Both analysis prompts now ask for `public_participation[]` (one row per named public speaker per item, with a stance
and a verbatim quote), which the bronze model already read but no prompt emitted. Two marts expose it per comment and
per decision. The reviewer traced the compile path, the contract columns and types, the join keys and the loader, and
found nothing that should fail, with three should-fix items; the missing enforced foreign key was fixed on the branch.
**The SQL has still never been parsed or built**, so the verdict is on the reading, and the PR stays a draft: it must not
merge until `dbt build --select bronze_public_participation_from_ai+` passes against the warehouse and the owner agrees,
because merging changes what every later analysis run emits.

## Scope of Change
- Files changed: 10 (excluding this review)
- Areas touched: prompts / packages (llm) / dbt_project / web_docs
- Commits: `7b6dd404` feat(llm): extract public-comment stance in the full and light analysis prompts, plus the
  review-fix commit that carries this file
- Range reviewed: `origin/main...origin/feat/807-public-comment-stance` at `7b6dd404`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Not run at review time (the bot's review commit became the head and does not trigger workflows). CI does not build dbt models. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. Nothing is served yet; a missing or unrecognised stance stays null and a
  decision without data has no row.
- Personal data: the rows name people who spoke at public meetings and quote them. That is public record, the same
  class as the existing `people[]` and `personal_stories`.
- Destructive or bulky data changes: none. A one-time `--full-refresh` of one small bronze model is recommended (below).

## Strengths
- Reuses a slot the pipeline already had; the loader keeps the new key (no allow-list of top-level keys).
- The `event_decision_id` formula matches `event_decision` exactly; a null item id yields a null link, as intended.
- Unknown is kept apart from neutral end to end.

## Findings
### 🔴 Blocking (Critical)
None found by reading. Building the models is still required.

### 🟡 Should fix (Important, non-blocking)
1. `_schema_public_comment.yml`: `event_meeting_id` had only a warn-level relationships test, but `event_meeting` has a
   single-column primary key (`macros/event_extractions.sql`), so a real foreign key is possible and `CLAUDE.md`
   requires it. **Fixed on the branch**: a model-level `foreign_key` constraint, the same shape as `_mdm_marts.yml`;
   comments corrected. Whether dbt-postgres accepts the constraint against that incremental table can only be shown by
   the build.
2. `bronze_public_participation_from_ai.sql`: the key now includes the item id. If an analysis is re-loaded, its
   new-format rows will not replace an old-format row. **Action after merge:** run the model once with `--full-refresh`
   (the table holds about one analysis today). Noted in the model and the design page.
3. `int_civic__item_signals.sql`: public-comment duration now sums one span per row, so a speaker with rows on several
   items adds each span. The speaker count is unaffected. Accepted and documented; dedupe in that CTE if one span per
   speaker is wanted.

### 🔵 Nits / suggestions (Minor)
- `public_stance_bucket`: an unrecognised value ("Unknown", "N/A") mapped to neutral. **Fixed**: it maps to null, and
  case, spaces and a trailing full stop are ignored.
- The bronze model's "about 1 of 1,569 analyses" note would go stale. **Fixed**: marked as the state before #807.
- `policy_analysis_part_1.md`: missing blank line before the new heading. **Fixed**.
- The light prompt's `firstname_lastname_role` slug differs from the full prompt's; the tiers never mix within one
  analysis, and two people with the same name and role would merge. Left as is.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #807 with the four parts; branch `feat/807-public-comment-stance`; `Closes #807` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | |
| dbt for transformations | Yes | The bucket mapping is a dbt macro; Python only validates shape |
| Naming | Yes | `state_code` and `state`; no `dim_`/`fact_` |
| Keys | Yes | A primary key on each mart; FK to `event_meeting` enforced; FK to the partitioned `event_decision` by relationships test, as `decision_speakers` does |
| Docs | Yes | `web_docs/docs/development/meeting-sentiment-design.md` |
| Tests | Partly | Schema and prompt-vocabulary tests; no dbt unit test for the macro or the marts |
| Shared libraries | Yes | `packages/llm` and `packages/datamodels` tests run |
| Paid compute | n/a | No run is started; the prompts change what later runs emit, which is why the PR is on hold |

Not required until the marts are served: the publish list, ODCS contracts and `data-contracts.md`.

## Test Coverage
`pytest packages/llm packages/datamodels/tests`: 336 passed, 1 failed (`test_jev_analyze_gate`, missing `yt_dlp`; it
fails the same way on `main` here). `python -m models.odcs --check` passes. Not run: `dbt parse`, `dbt build`, any
analysis with the new prompts.

## Verdict
approve-with-nits on the reading. Before merge: build the models against the warehouse, get the owner's go-ahead, and
plan the one-time full refresh.
