---
sidebar_position: 46
title: Why videos failed (Batch Job Status)
description: Click the red failed count on the Videos or Transcripts row to see the reasons behind it, grouped, with the videos for each (#792).
---

# Why videos failed

Issue [#792](https://github.com/getcommunityone/open-navigator/issues/792).

On **Admin → Batch Job Status**, the Videos and Transcripts rows show a red failed count. Click it to open
`/admin/batch-jobs/failures?stage=…&cohort=…&state=…`.

## What the page shows

- **A title that states the scope exactly:** the stage, the Filter (cohort), and the state or "All states". The same
  three values are in the URL, so a refresh or a shared link shows the same numbers.
- **Reason groups,** biggest first, each with its count, its share, and a short "what to do" line.
- **Raw error text** under each group, merged only where messages differ by a long number (an id, a byte count).
  Click one to list its videos (YouTube link, title, jurisdiction, state), 50 at a time.
- **An empty state** ("No failed videos recorded for this scope") when nothing failed. No placeholder numbers.

## Where the numbers come from

The count is the number of rows in `bronze.bronze_event_youtube` whose `transcript_file_error` is not NULL, with the
same cohort and state filters as the stage report. Videos and Transcripts show the same number because both count
those rows. The reason counts add up to that total.

| Group | Matches text such as | What to do |
|---|---|---|
| YouTube blocked the request (bot check) | "Sign in to confirm you're not a bot" | Refresh `youtube_cookies.txt`; check the VPN |
| Rate limited or over quota | "429", "Too Many Requests" | Wait, retry a smaller batch |
| No captions on the video | "Subtitles are disabled", "No transcripts were found" | Not fixable; stays failed |
| Video private, removed or restricted | "Video unavailable", "This video is private" | Not fixable; stays failed |
| Network, proxy or VPN problem | "proxy", "timed out", "connection" | Check VPN and proxy; retry |
| No reason recorded | an empty error | Re-run the step and read its log |
| Other | anything else | Read the raw text; if it repeats, add a group |

Groups are chosen by keyword on the stored text (`api/batch_jobs/failure_reasons.py`). The raw text is always shown, and
text that matches nothing is "Other", never reworded.

## API

- `GET /api/batch-jobs/failure-reasons?stage=transcripts|videos&cohort=&state=` → `{total, groups[]}`
- `GET /api/batch-jobs/failures?stage=&cohort=&state=&reason_id=&limit=&offset=` → `{total, rows[]}` (`reason_id` is the short md5 id each reason carries, so long messages never travel in the URL)
- `POST /api/batch-jobs/failures/retry` (admin) `{stage, cohort, state, group | reason_id, dry_run}` → `{matched, made_due, already_due}`. Releases the matching videos from the 30-day cooldown in `bronze.bronze_transcript_fetch_attempts`; deletes nothing. The next Backfill on the Transcripts row fetches them. Only the retryable groups (bot check, rate limit, network, not yet available, unknown, other) accept it; "No captions" and "unavailable" return 400.

Each reason line links to the YouTube video of an example failure ("Watch an example") and shows URLs in the message as links. Reasons are merged when they differ only by video id or number. Groups are chosen from the cause text (after "most likely caused by:"), so the shared opening sentence no longer puts every failure under "No captions".

Only the Videos and Transcripts stages have a breakdown. The other stages record their failures elsewhere and do not
link to this page.

## The grid of failed items (#800)

Every stage row with a red failed count (Videos, Transcripts, Analysis light, Reports light, Analysis full, Reports full)
opens `/admin/batch-jobs/failures?stage=&cohort=&state=`. The title names the stage, Filter and state in effect.
Under the reason cards (Videos and Transcripts only, because they read `transcript_file_error`) sits **All failed items**,
a grid with one row per failed video:

- Columns: video (id), title, jurisdiction, state, channel, meeting date, meeting type, error, reason group, last changed.
  Click a header to sort ascending, then descending. Only the allow-listed columns sort.
- Search (title, video id, jurisdiction, error text), reason group and state filters; page size 25, 50 or 100 with
  first, previous, next and last. Sort, page, size and filters stay in the URL (`q`, `group`, `sort`, `dir`, `page`, `size`),
  so a refresh or shared link shows the same rows.
- Click a row for the full error, every id with copy buttons, links to the video and channel, what to try for its reason
  group, and where to look (the step's log on Batch Job Status).
- The count above the grid equals the failed count on the stage row for the same scope when no search or group filter is set.

| Stage | Error column on `bronze.bronze_event_youtube` |
|---|---|
| videos, transcripts | `transcript_file_error` |
| analyses_light | `policy_analysis_error` |
| reports_light | `policy_report_error` |
| analyses_full | `policy_analysis_full_error` |
| reports_full | `policy_report_full_error` |

`GET /api/batch-jobs/failure-grid?stage=&cohort=&state=&q=&group=&sort=&dir=&limit=&offset=` returns
`{stage, cohort, state, error_column, where_to_look, total, columns[], rows[]}`. `sort` must be one of `video_id`, `title`,
`state_code`, `jurisdiction_name`, `error`, `last_updated`, `event_date`, `meeting_type`; any other value is a 422 and no request
text reaches SQL. Tests: `tests/test_failure_grid_800.py` (the SQL checks run when `TEST_PG_DSN` points at a Postgres).
