---
pr: 1263
branch: feat/1255-meeting-audio-onedrive
title: "feat(scrapers): download 2026 data-center meeting audio to the owner's personal OneDrive"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent (python-packages-specialist) and coordinator; supersedes the github-actions auto-review of edc8e6f9
verdict: approve-with-nits
---

# PR Review: download 2026 data-center meeting audio to the owner's personal OneDrive

## Summary
The PR adds `python -m scrapers.youtube.download_meeting_audio`. It selects the 2026 data-center meetings (942 videos after `meeting_video_kind` drops 34 non-meetings) and builds a by-`video_id` inventory of the audio we already hold. It downloads only what is missing, one file at a time through a temp dir, then uploads each file to the owner's personal OneDrive with rclone, checks the size and stamps the bronze tracking columns. The reviewer found no Critical issues, 5 Important and 6 Minor. Four of the Important findings were verified and are fixed in 63b05fe6, each with a test: tracking split across duplicate rows, legacy-name collisions across channels, a mismatched-size copy left on the target, and a DB failure with no rollback. The fifth Important finding (cookies and browser headers) is covered by the owner's recorded exception, and the decision page now says so plainly. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 6 (+1416 / -3, excluding this review file)
- Areas touched: packages (scrapers, hosting migration), web_docs
- Commits:
  - edc8e6f9 feat(scrapers): download 2026 data-center meeting audio to the owner's personal OneDrive
  - 63b05fe6 fix(scrapers): review fixes for the meeting audio downloader (#1255)
  - plus the bot auto-review commit and a merge of it
- Range reviewed: `merge-base(origin/main)..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | read before merge (see PR checks) |
| Documentation Build | read before merge |
| Backend Tests | read before merge |
| API Types | read before merge |
| PR conventions | read before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The PR does not commit the cookies file and holds no credentials. The rclone token lives in the owner's `~/.config/rclone`, outside the repo.
- **Fabricated data:** clean. Nothing changes in a served path. The dry-run figures come from warehouse durations, and the code says where it uses an average for missing durations.
- **Personal data:** clean. It handles public government meeting recordings only and adds no people data.
- **Privacy and data ethics:** the scraper downloads from YouTube against its terms. The owner made a recorded exception (decision page, 2026-11-27). The tool keeps the limits: one file at a time, 8 s plus jitter between files, a pause that doubles on 403/429/bot checks, and a stop after 3 in a row. It uses no proxies, no new cookies and no custom UA, and goes through the VPN guard (#488). Not blocking, under the documented exception.
- **Destructive data changes:** none. It deletes only its own per-video temp dir and, on a size mismatch, its own just-uploaded copy. `data/cache` is read only. The new bronze table is additive (migration 116).

## Strengths
- The rule "never download twice" holds at every layer: the target listing, the tracking columns, local caches, and a `video_id` anywhere in a filename.
- The disk footprint is bounded: one temp file at a time, and the C: synced folder is never touched.
- Blocks stop the run; nothing escalates.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All four verified items are fixed in 63b05fe6:
1. `scope_sql` picked a single bronze row per video, so a tracking stamp on a duplicate row was missed. It now aggregates (`max`, `array_agg FILTER`). Test: tracked rows are skipped.
2. A legacy `date_title` match could claim another town's file. The match now requires the legacy folder to end in this channel's id. Tests cover the cross-channel and same-channel cases.
3. A size mismatch left a bad copy that the next run would count as held. `store_verified` now removes it. Test: `test_size_mismatch_removes_our_copy`.
4. A DB error left the connection aborted. It now rolls back and is counted as "stored but not recorded". Test: `test_db_failure_after_upload_rolls_back_and_continues`.
5. Cookies and browser headers: kept by owner instruction ("use the repo's existing cookies file only if it already exists"). The decision page now names the signed-in session and the headers.

### 🔵 Nits / suggestions (Minor)
- Fixed: the dry run no longer writes; rclone stderr is surfaced; `--no-transcode` is a parameter; in-scope videos missing from bronze are kept, with a warning; an unlisted target makes the plan print an upper-bound warning.
- Issue contract path changed by owner direction (existing `CommunityOne/youtube_audio` folder). A dated comment was added to #1255.
- Open: the tracked-path suffix match could match a very short root-level name. Low risk, left as is.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1255 has all four parts; follow-up #1256 (portals) filed |
| Conventional Commits | yes | co-author trailers present |
| No fabricated data | yes | |
| New Python in `packages/` | yes | `python -m scrapers.youtube.download_meeting_audio`; nothing in `scripts/` |
| dbt for transformations | yes | ingestion and tracking writes only; no transformations |
| Naming / Keys | n/a | bronze table with PK `(video_id, location)`; not in `public` |
| Docs | yes | decision page + README section; sidebar entry |
| Telemetry and logging | yes | loguru |
| Tests | yes | 16 unit tests |
| Shared libraries | yes | new module only; scrapers tests for it pass |

## Test Coverage
- Ran `pytest packages/scrapers/tests/test_download_meeting_audio.py`: 16 passed. `ruff check` and `ruff format` are clean.
- Live: the dry run against the local warehouse, and one real download to a scratch folder (`--no-record`, kept for a later upload, not downloaded again). The ffmpeg re-encode took it from ~99 kbps to 59 kbps.
- Not covered: the real rclone upload. It is blocked until the owner signs in to OneDrive.

## Verdict
approve-with-nits. Merge once the required CI is green.
