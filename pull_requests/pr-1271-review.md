---
pr: 1271
branch: feat/1270-audio-gdrive-target
title: "feat(scrapers): meeting audio goes to the owner's Google Drive via rclone gdrive"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator (small follow-up to #1263, which had a subagent review); supersedes the github-actions auto-review
verdict: approve
---

# PR Review: meeting audio goes to the owner's Google Drive via rclone gdrive

## Summary
This follow-up to #1263 changes the default destination to the owner's Google Drive, which he named on 2026-11-27. The rclone target is renamed to `RcloneTarget`, and the defaults are now `--target rclone --remote gdrive --remote-root CommunityOne/youtube_audio`. The `onedrive`/`gdrive` target names still work as aliases, and `--target local` is unchanged. The docs now say Google Drive. The download, upload, verify, delete-temp flow and the no-redownload inventory from #1263 are untouched. Verdict: approve.

## Scope of Change
- Files changed: 4 (module, tests, README, decision page)
- Areas touched: packages, web_docs
- Commits: abee38af feat(scrapers): meeting audio goes to the owner's Google Drive via rclone gdrive (plus the bot auto-review commit)
- Range reviewed: `merge-base(origin/main)..HEAD`

## CI Status
| Check | Status |
|---|---|
| Required checks | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No rclone token or account details in the repo.
- **Fabricated data:** clean. No served path.
- **Personal data:** clean. The owner's account email is deliberately left out of the docs.
- **Privacy and data ethics:** unchanged from #1263, still under the documented owner exception.
- **Destructive data changes:** none.

## Strengths
- The rclone target is generic now, so a later change of destination is one flag.
- The missing-remote message gives the exact one-time command and warns against the Drive-for-desktop mount.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `audio_file_path` values written earlier would still carry an `onedrive:` prefix. None were written, because OneDrive was never signed in, so nothing needs migrating.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1270, four parts |
| Conventional Commits | yes | |
| New Python in `packages/` | yes | |
| Docs | yes | README + decision page updated in the same PR |
| Telemetry and logging | yes | loguru |
| Tests | yes | defaults and local target tested; 18 passed |

## Test Coverage
Ran `pytest packages/scrapers/tests/test_download_meeting_audio.py` (18 passed) and `ruff check` (clean). Also ran a live dry run against the local warehouse, which reports the missing `gdrive` remote and prints the plan.

## Verdict
approve. Merge once the required CI is green.
