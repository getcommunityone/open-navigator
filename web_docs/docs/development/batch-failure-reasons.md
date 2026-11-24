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
