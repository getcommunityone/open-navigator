---
pr: 837
branch: fix/836-load-dbt-selects-participation
title: "fix(batch-jobs): rebuild every analysis bronze model in the Load tab's dbt step"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: fix(batch-jobs): rebuild every analysis bronze model in the Load tab's dbt step

## Summary
The Load tab's dbt step built marts on top of bronze tables it had not refreshed. One of them, `public_comment` from
#813, fails outright when its bronze parent lacks the new columns, which marks the whole Load run failed; the others
(`event_meeting`, `event_topic`, `event_place` and so on) were silently built from stale data. The PR adds the nine
missing `bronze_*_from_ai` models to the selection. Approve with nits: the lineage was read from the model files and
dbt itself was not run.

## Scope of Change
- Files changed: 3 (excluding this review)
- Areas touched: packages (hosting) / tests / web_docs
- Commits: `b70b600e` and the follow-up that drops the `+` from the added selectors
- Range reviewed: `origin/main...origin/fix/836-load-dbt-selects-participation`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. CI does not run dbt. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. The step still runs `dbt run` against the local warehouse only.

## Strengths
- The cause was traced to the model files, and the fix is guarded by a test tied to the files on disk.
- The first version's reach was measured before it shipped (below) and cut back.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
1. The first commit selected the bronze models with `+`. Walking the `ref()` graph showed that grew the step from 62
   models to 112: the descendants of the persons, places and organizations models include the MDM clustering
   (`mdm_person`, `mdm_organization`, their bridges and serving views). A load should not rebuild that. **Fixed in the
   second commit:** the added models are selected bare, giving 71 models, and a script over the same graph confirms no
   selected mart is left with an unselected `*_from_ai` parent.

### 🔵 Nits / suggestions (Minor)
- The failure of `public_comment` on the owner's warehouse is inferred from the lineage and the model SQL; there is no
  dbt log to confirm it. The fix is correct either way: a mart must not be built ahead of its parent.
- `event_organization` descends only from `bronze_organizations_from_ai`, so the step refreshes its parent but does
  not rebuild it. It was not rebuilt before either. Worth its own decision.
- The graph was walked with a regex over `ref('...')`, not `dbt ls`. A `ref` written another way would be missed.
- Step time will rise by nine incremental models; not measured.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #836 with the four parts and a dated contract change; branch `fix/836-load-dbt-selects-participation`; `Closes #836` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| dbt DAG checked before changing | Partly | Walked from the model files; `dbt ls` could not run in the session |
| Docs | Yes | `web_docs/docs/development/batch-load-tab.md` |
| Tests | Yes | The selected list must equal the analysis bronze models on disk; only the two mart roots take `+` |

## Test Coverage
`pytest tests/test_load_tab_steps_796.py tests/test_load_tab_counts_823.py tests/test_deployments_groups_796.py`: 50
passed. Not run: dbt.

## Verdict
approve-with-nits. On the first real load, open the dbt step on the Load tab: its counts and any failed model are now
shown there.
