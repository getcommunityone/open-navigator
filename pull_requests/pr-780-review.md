---
pr: 780
branch: fix/777-shared-channel-video-routing
title: "fix(youtube): file shared-channel videos under the government their title names"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: python-packages-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(youtube): file shared-channel videos under the government their title names

## Summary
Fixes #777. Channel `UCZ47nYYggC17NbmBs0Mx3Ww` (49 County News.Net) is linked to seven Marion County, AL towns, and the loader filed every new video under whichever town it refreshed, so 10 Hamilton City Council videos landed under Winfield. The loader now leaves a video to a sibling jurisdiction when the title names exactly one jurisdiction linked to the same channel, and a new dry-run-by-default CLI plans the correction for existing rows (682 moves, 1,140 unresolved, nothing written). The reviewer's Important finding (the first version's guard ran on every channel and would drop legitimate videos) was fixed in f42c44db, along with the county `city` value. Approve with nits. The data write (`--apply`) is held for the owner.

## Scope of Change
- Files changed: 5 (see `git diff --shortstat`), areas: packages (scrapers), web_docs
- Commits:
  - 860a936b fix(youtube): correct #777 videos through the attribution override seed
  - 729368dc fix(youtube): file shared-channel videos under the government their title names
  - f42c44db fix(youtube): skip a shared-channel video only when it names a linked sibling
- Range reviewed: `origin/main..860a936b`

## CI Status
| Check | Status |
|---|---|
| Frontend Build / Documentation Build / Backend Tests / API Types | pending on the new head at time of writing |
| PR conventions | pending |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean (pre-commit secret hooks passed; the DSN is built from the environment, with no literal credentials).
- Fabricated data in a served path: clean (no `api/` or `web_app/` changes).
- Personal data: clean (public meeting videos only).
- Destructive data changes: the CLI has an `UPDATE` behind `--apply`, in one transaction, guarded by the old `jurisdiction_id`; it changes no keys and deletes nothing. It has **not been run**. Dry run only.

## Strengths
- The root cause is traced to the row level (writer signature `channel_type=unknown`, `datasource_id=video_id`, 2026-11-22/23) and to the code path (`process_jurisdiction` plus the last-writer-wins upsert).
- Reuses the existing `title_names_other_government` guard instead of a new matcher.
- The correction is conservative (it moves only on an unambiguous sibling), read-only by default, defaults to localhost:5433 and never Neon, and writes a CSV plan.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- ~~`load_youtube_events_to_postgres.py` guard applied to every channel (a city channel's county-commission videos dropped for good)~~. **Fixed in f42c44db**: the guard now skips only when the title names a linked sibling. Covered by `test_loader_split_keeps_a_government_not_linked_to_the_channel` and `test_loader_split_single_jurisdiction_channel_keeps_everything`.

### 🔵 Nits / suggestions (Minor)
- ~~The CLI wrote a county's name into `city`~~. **Fixed in f42c44db** (`city` is cleared for a county target).
- `get_jurisdictions_from_counties_scraped` defaults a NULL `jurisdiction_type` to `county` (line ~1126, pre-existing). A NULL-typed city would be checked as a county. Not introduced here; no change.
- Each refresh adds one small sibling query per channel. It is negligible next to the YouTube fetch.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `fix/777-...`, `Closes #777`, the issue has all four parts; follow-ups #778 and #779 opened |
| Conventional Commits | Yes | Both commits, with the co-author trailer |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | `python -m scrapers.youtube.reassign_shared_channel_videos`; nothing in `scripts/` |
| dbt for transformations | Yes | A bronze ingestion-assignment correction, as the issue's Contract allows ("reviewed script"); marts rebuilt via dbt afterwards |
| Naming / Keys / Calendar years | n/a | No model changes; `video_id` PK untouched |
| Docs | Yes | `web_docs/docs/data-sources/youtube-discovery.md` updated |
| Telemetry and logging | Yes | loguru |
| Tests | Yes | `test_shared_channel_video_routing.py`, including a wiring test that fails against `main`'s loader |
| Shared libraries | Yes | `pytest packages/scrapers/tests`: 346 passed, 1 skipped (the civicsearch modules can't import locally because `aiolimiter` is missing, which is unrelated) |

## Test Coverage
Covered: the helpers on verbatim Winfield/Hamilton titles, the no-sibling and non-linked-government cases, the `process_jurisdiction` wiring, and `plan_moves`. Run locally:
- `pytest packages/scrapers/tests` → 346 passed;
- `ruff check` on the new files;
- `web_docs` build → success;
- the CLI dry run (read-only), and the sibling SQL run read-only against localhost:5433.

Not covered: `--apply` against a database (deliberately not run).

## Addendum (860a936b)
The correction now goes through the existing #514 path instead of a direct UPDATE. `--write-seed` adds the 682 planned moves as per-video rows (issue 777, verbatim title as evidence) to `dbt_project/seeds/youtube_channel_attribution_override.csv`, and `repair_youtube_channel_attribution` applies them.

Verified by reading the macro and model:
- Per-video rows don't trigger the catalog steps 2–4, including the `int_events_channels` delete: those steps read only rows where `video_id` is empty.
- `int_youtube__attribution_override` emits only videos that have a per-video or channel-default row, so other videos on these channels are untouched.
- `city` is set only for municipalities, which supersedes the earlier county `city` nit.

The CLI is now read-only end to end. Tests: 10 passed, including `test_seed_rows_skip_listed_and_unresolved`. The seed has not yet been loaded into the warehouse.

## Verdict
approve-with-nits. Merge waits for the owner: the PR ships a tool whose `--apply` changes warehouse rows, and the owner reserved that write.
