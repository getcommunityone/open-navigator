---
sidebar_position: 32
title: Jev transcript screening
description: Screening meeting transcripts with TypeSafe's Jev before the paid Gemini analysis, so videos with no decisions can be left out of the batch.
---

# Jev transcript screening

Gemini's transcript analysis writes the decisions, quotes, amounts and speakers that the site shows, and it's billed
per call. Many captioned videos hold nothing to analyze: ceremonies, trainings, press conferences, videos that aren't
from a government at all. [Jev](https://docs.typesafe.ai/introduction), TypeSafe's decision model, can answer typed
questions about a transcript for a small fraction of that cost, so it screens transcripts first and the batch can leave
out the ones with no decision in them.

## In short

- **Jev doesn't replace the analysis.** It returns labels and probabilities, never text, so it can't extract a
  decision, a quote or a dollar amount. It only decides what's worth sending to Gemini.
- **Three questions per transcript:** what kind of video it is (Choice), whether the body votes on or approves
  anything (Noul), and whether a data center is discussed (Noul).
- **Nothing is skipped by default.** `batch_backlog submit --skip-jev-below P` leaves out videos whose screen gives
  a decision probability below `P`. Unscreened videos are always sent.
- **The screen never changes a transcript.** It writes its own table. The existing non-meeting exclusion
  (`llm.gemini.policy_exclusions`) deletes the transcript text, which is too destructive for an automatic screen.
- **Price:** $0.042 per million input tokens, and output is free
  ([models page](https://docs.typesafe.ai/models.md), read November 15, 2026). The price is in
  `packages/llm/src/llm/usage/prices.yaml`, so `python -m llm.usage.report` shows what each run cost.

<details>
<summary>How to run it</summary>

Put a key from the [TypeSafe console](https://console.typesafe.ai/keys) in `.env` as `TYPESAFE_API_KEY`.

```bash
# Count the transcripts and estimate the tokens; sends nothing
.venv/bin/python -m llm.typesafe.screen_transcripts --state AL --limit 50 --dry-run
# Screen them
.venv/bin/python -m llm.typesafe.screen_transcripts --state AL --limit 50
# Batch analysis that leaves out screened videos unlikely to hold a decision
.venv/bin/python -m llm.gemini.batch_backlog submit --state AL --skip-jev-below 0.2 --dry-run
```

`--jurisdiction-id` screens one place, and `--rescreen` screens videos again. A video is screened again on its own
when the questions' wording changes (`question_version`).

</details>

<details>
<summary>Where each piece lives</summary>

| Piece | Where | What it does |
|---|---|---|
| Client | `llm.typesafe.client` (`JevClient`, `choice`, `score`, `noul`) | `POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer $TYPESAFE_API_KEY`. Retries 429 and 529 with backoff. Writes one usage row per call (`provider = "typesafe"`) |
| Screen | `python -m llm.typesafe.screen_transcripts` | Reads captioned videos from `bronze.bronze_event_youtube_transcript`, newest first, and asks the three questions |
| Table | `bronze.bronze_transcript_screen_jev` | One row per video. PK `video_id`. `meeting_kind` and its probabilities, `has_decisions_p`, `mentions_data_center_p`, chunk counts, input tokens, the raw answers, `question_version`, `screened_at` |
| Gate | `llm.gemini.batch_backlog submit --skip-jev-below P` | Leaves out videos whose current screen has `has_decisions_p < P` |

</details>

<details>
<summary>Long transcripts</summary>

Jev reads at most 32k tokens per question and 64k per request. A council meeting's transcript is often longer, so the
screen cuts it into chunks of about 100,000 characters (about 25k tokens), breaking between caption segments. It
screens up to four evenly spaced chunks, always the first and the last (`--max-chunks`, `--chunk-chars`).

- `meeting_kind` averages the chunks' probabilities.
- Each yes/no answer takes the highest chunk. A vote anywhere in the screened chunks counts, so a video is only
  skippable when none of them shows one.

Jev also offers a long-context header that raises the limits, but TypeSafe says it's slower and less accurate, so the
screen doesn't use it.

</details>

<details>
<summary>Decisions and why</summary>

- **Screen, don't replace.** The site's rules require every filtered tile to show a verbatim quote from the record,
  and Jev can't produce text. Gemini stays the extractor.
- **Opt-in skipping.** Jev's probabilities are calibrated on TypeSafe's data, not on our meetings. Before relying on
  `--skip-jev-below`, screen a few hundred videos that Gemini has already analyzed and check how often a video with a
  low `has_decisions_p` turned out to have decisions. Pick the threshold from that, and record it here.
- **httpx, not the official SDK.** `typesafe-sdk` would work too. The workspace already depends on httpx, and this
  way every call goes through the same usage log as Gemini.
- **Not yet checked against the live API.** The client and screen are tested against recorded response shapes from
  TypeSafe's docs. The first real run should be a `--limit 20` on a state whose analyses are already done.

</details>
