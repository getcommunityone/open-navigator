---
sidebar_position: 32
title: Data center jobs claims
description: How jobs promised in public meetings are extracted, stored, served and shown, and who promised them (DC-1.1, DC-1.2).
---

# Data center jobs claims

Residents asked whether the jobs promised for a data center are real. DC-1.1
([#246](https://github.com/getcommunityone/open-navigator/issues/246)) records every jobs claim made in an analyzed
meeting, split by phase, with the speaker and the words they used. It is part of the
[Data Center Accountability epic](https://github.com/getcommunityone/open-navigator/issues/236).

## The path of a claim

| Step | Where | What it holds |
|---|---|---|
| Extraction | `prompts/policy_analysis_part_1.md`, `job_claims[]` | One object per claim per phase: headcount range, dates, project, speaker, timestamp, verbatim quote |
| Bronze | `bronze.bronze_events_analysis_ai.structured_analysis` | The analysis JSON, as for every other `*_from_ai` extraction |
| Staging | `staging.stg_job_claim_ai` (view) | Each claim typed, with guarded casts; rows that break the rules are kept so warn tests count them |
| Mart | `job_claim` (gold, published to `public`) | One row per claim per meeting. PK `job_claim_id`; FK `jurisdiction_id` → `jurisdictions` |
| API | `GET /api/data-centers/job-claims?state=&city=&jurisdiction_id=&limit=` | Each claim with `speaker_role` and `body_name` (DC-1.2). The data center claims for the scope (newest first), the scope echoed back, and the claims per phase for the whole scope (`totals`). `city` matches a substring of the city or the jurisdiction name, as the browse routes do |
| UI | `/data-centers?state=&city=` | Construction and operations side by side, with the quote, who said it (with role), the meeting body, and a link to the moment on the meeting page |

## Who promised it (DC-1.2)

[DC-1.2](https://github.com/getcommunityone/open-navigator/issues/247) attributes each claim, so a resident can hold the right person to it.

- **Speaker and role.** The extraction adds `speaker_role` (the role said in the meeting: "applicant", "District 3 council member", "resident") and `speaker_person_id` (the speaker's entry in the same analysis's `people[]`). Staging fills a missing name or role from that `people[]` entry. Otherwise the role stays null; it's never inferred from a name.
- **Which meeting.** `job_claim.body_name` comes from `event_meeting.body_name` (for example "Tuscaloosa City Council"). The page says "At the Tuscaloosa City Council meeting", or "Meeting record" when the body isn't recorded.
- **The moment.** Each claim uses the shared `CitationLink` from [CORE-2.1](https://github.com/getcommunityone/open-navigator/issues/240): "Said by Dana Ruiz, applicant · Mar 2, 2026 · ▶ 12:34". The link opens `/meetings/<event_meeting_id>?t=754`, the meeting page with the recording started at that second. Without a timestamp it opens the meeting and says "time not recorded"; without a speaker it says "Speaker not identified".
- **Re-analysis needed.** Meetings analyzed before this change have no `speaker_role` or `speaker_person_id`, so their claims show the name only until they are re-analyzed with the updated prompt.

Job-application links for these projects, and how they're kept current: [Data center application links](./data-center-application-links.md) (DC-1.3).

## Rules

- **Never one combined jobs number.** A claim of "1,200 during construction and 50 permanent" is two rows, one per
  phase, and the page shows them in separate columns.
- **Unknown is null, never 0.** No number said ("lots of jobs") means no headcount, and the page shows "Not stated".
  One bound only reads as such: "up to 300" shows "Up to 300 jobs" and "at least 200" shows "At least 200 jobs",
  never an exact figure. Counts on the page are the scope's real totals; a cut list says so ("showing the latest N"). A year or month alone is not a
  date.
- **No quote, no row.** The mart drops claims without their verbatim words or with a phase other than construction
  or operations.

## Decisions

- **`person_id` is empty for now.** No person index has been chosen to match speakers against, so `job_claim` carries
  `speaker_name` as said and leaves `person_id` null, without a foreign key, until that index exists.
- **The link to `event_meeting` is a test, not a constraint.** `event_meeting` gets its primary key from a bootstrap
  macro run by hand, so a foreign-key constraint would fail on a build where it hasn't run. The mart inner-joins
  `event_meeting`, so every claim has its meeting; a warn-level relationships test reports any gap.
- **`jurisdiction_id` comes from the video.** `event_meeting` has no jurisdiction id, so `job_claim` resolves it
  through `event_youtube_with_jurisdiction` on `video_id`, and keeps it only when `jurisdictions` has it.

## Checked

On November 14, 2026, a made-up council meeting with a data center rezoning and a warehouse abatement was analyzed
with the updated prompt on `gemini-3.5-flash-lite` and `gemini-3.8-flash`. Both models returned the construction
claim (1,200 workers, March 1, 2027 to June 30, 2028), the operations claim (40 to 50 jobs) and the warehouse claim
("up to 300"), each with its verbatim quote and speaker, and neither combined the phases. "Lots of jobs", with no
number, produced no row. 3.5 Flash-Lite put one claim's timestamp 20 seconds before its transcript cue; 3.8 Flash
got it right. A meeting with no jobs claims returned an empty `job_claims` array.

Not yet checked against real meetings or the warehouse: that needs the extraction run on real transcripts and
`dbt build --select +job_claim`.
