---
pr: 440
branch: fix/429-youtube-loaded-at
title: "fix(youtube): set loaded_at when a video is first loaded"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review in a fresh worktree; each finding traced in the code)
verdict: approve-with-nits
---

# PR Review: fix(youtube): set loaded_at when a video is first loaded

## Summary
Both YouTube loaders (`ingestion.youtube.events._UPSERT_YOUTUBE_SQL` and
`scrapers.youtube.load_youtube_events_to_postgres.YouTubeEventsLoader.insert_events`) now set `loaded_at = NOW()` on
insert and leave it alone on conflict, and migration 113 sets the column default to `now()` for any other writer.
Existing NULLs stay NULL, as issue #429 asks. The change is small and correct. The new SQL comments don't create stray
bind parameters (checked on the compiled `text()`), and the two new tests fail on the old code. Approve with nits.

## Scope of Change
- Files changed: 4 (+55 / -4)
- Areas touched: packages (ingestion, scrapers, hosting migration)
- Commits:
  - 6145c889 fix(youtube): set loaded_at when a video is first loaded
- Range reviewed: `fb865cc2..6145c889`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker changes) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. Old rows aren't backfilled with a made-up load time.
- Personal data: clean.
- Destructive or bulky data changes: clean. Migration 113 only adds a column default to a bronze table owned by the
  migrations folder; reversible, and the undo is in the file.

## Strengths
- Insert-only semantics, so `loaded_at` keeps meaning "first loaded".
- Leaves historic NULLs alone rather than inventing a time, with the reason in the migration.
- A default at the table level covers writers the PR doesn't touch.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **Left.** `packages/ingestion/tests/test_youtube_loaded_at.py` checks the SQL text: `"loaded_at =" not in update`
   would miss `loaded_at=EXCLUDED.loaded_at` written without spaces. A regex such as `r"\bloaded_at\s*="` would be
   tighter.
2. **Left.** The same file tests the `scrapers` loader from `packages/ingestion/tests`. It works (pytest.ini puts both
   on the path), but the scrapers test belongs in `packages/scrapers/tests`.
3. **Left.** Once this merges, #437's freshness check on `bronze_event_youtube` could move from `last_updated` to
   `loaded_at` for new rows. #437 keeps `last_updated` because older rows are NULL, and its comment now points here.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `fix/429-youtube-loaded-at`; `Closes #429`; the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | Changes are in package modules |
| dbt for transformations | n/a | Ingestion only |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | n/a | |
| Telemetry and logging | Yes | Unchanged loguru |
| Tests | Yes | 2 regression tests |
| Shared libraries | Yes | `ingestion` and `scrapers` suites run |

## Test Coverage
Ran locally: `pytest packages/ingestion/tests packages/scrapers/tests -q` → 758 passed. With the two loaders reset to
the base commit, `test_youtube_loaded_at.py` → 2 failed, so the tests catch the bug. `ruff check` on the changed
ingestion files: clean. Compiled `_UPSERT_YOUTUBE_SQL` from the worktree: its bind parameters are exactly the expected
columns (the comment's colon makes no `:set` parameter). Migration 113 was not applied by this review.

## Verdict
Approve with nits; nothing must change before merge.
