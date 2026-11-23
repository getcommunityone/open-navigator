---
pr: 771
branch: fix/770-discover-last-activity
title: "fix(batch-jobs): stamp each jurisdiction Discover tries so Last activity moves"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: claude-code
verdict: approve-with-nits
---

# PR Review: fix(batch-jobs): stamp each jurisdiction Discover tries so Last activity moves

## Summary

Closes #770. Discover's Last activity now moves as `discover --load` works: each county searched and each channel
loaded stamps `channel_checked_at` on its scraped row, and the dashboard reads the later of that and `discovered_at`.
Reviewed against `.claude/review-rubric.md`, `AGENTS.md` and `CLAUDE.md`.

## Scope of change

- `packages/scrapers/src/scrapers/youtube/discover_progress.py` (new): the column and the two stamps.
- `load_missing_county_channels.py`: `on_checked` callback; `discover_one_state` stamps on its own connection.
- `load_youtube_for_jurisdiction.py`: `load_and_stamp` stamps after every load, including a failed one.
- `api/batch_jobs/batch_job_db.py`: `discover_last_at_sql`, used by both Discover queries in `pipeline_stage_report`.
- Tests: `packages/scrapers/tests/test_discover_progress.py`, `tests/test_discover_last_activity_770.py`.
- Docs: `web_docs/docs/development/batch-analysis-light-full-design.md`.

## Checks

- The 13 new tests failed before the change and pass after it.
- Every test that references the changed modules: 52 passed, 2 skipped (with `pytest-asyncio` installed).
- No live database here: the first run after merge is the end-to-end check. Discover's Last activity should show
  minutes, not hours, a few seconds after a county finishes.

## Findings

### Blocking

None.

### Should fix

None.

### Nits

- If the `ALTER TABLE` can't get its lock within the lock timeout, the column isn't marked ready and every stamp
  tries again. Each try is bounded by the timeout and only warns, so a run is never stopped, but the log can repeat
  the warning until the lock frees.
- The stamps are an extra `UPDATE` per county and per channel load: small next to the YouTube calls each one follows.
- `data-model-erd.md` doesn't cover the scraped tables, so the new column is documented in the batch design page
  instead. The issue's Done when named the ERD page; a dated line on #770 records the change.

## Rules

- Data: the column follows the table's own naming (`discovered_at`, `channel_checked_at`). Bronze bookkeeping, not
  a transformation, so no dbt change. `discovered_at` keeps its meaning.
- Failures: a stamp that fails rolls back and warns; a failed load is still stamped, then re-raised.
- Issue first with four parts (#770); branch `fix/770-discover-last-activity`; `Closes #770`; docs in the same PR.

## Verdict

**approve-with-nits**: ready to merge when CI is green.
