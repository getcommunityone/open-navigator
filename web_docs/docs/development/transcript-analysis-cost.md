---
sidebar_position: 31
title: Transcript analysis cost
description: What each transcript-analysis call costs, what was changed to cut it, and how to run the backlog as a batch.
---

# Transcript analysis cost

The transcript pipeline (`python -m llm.gemini.meeting_transcript_policy`, driven over the backlog by
`python -m llm.gemini.analyze_backlog`) sends each meeting's transcript to Gemini with a 32 KB prompt and gets a
JSON analysis back. This page records what was changed to make each call cheaper and faster, why, and how to run
the backlog through the Batch API. The numbers come from the usage log described in
[LLM and GPU usage tracking](./llm-usage-tracking.md).

## What changed for every call (#263)

| Change | Why | How to undo it |
|---|---|---|
| Thinking is off (`thinking_budget=0`) on `gemini-2.5-flash*` | `gemini-2.5-flash` thinks by default, and thinking tokens are billed as output | `--thinking-budget -1` (the model's default) or a number; env `GEMINI_THINKING_BUDGET` |
| Part 1 asks for JSON output | The response was free text, searched for a JSON object | `--no-json-mode` |
| The fixed prompt comes first in the message | The per-video block used to come first, so no two calls shared a prefix and Gemini's implicit caching never applied | none: the same three parts, reordered |
| ~~The backlog leads with `gemini-2.5-flash-lite`~~ Reverted: Flash leads | Flash-Lite reversed a vote in the first comparison (below) | `--models gemini-2.5-flash-lite,gemini-2.5-flash` |
| Clients use API version `v1beta` | `google-genai` 3.x defaults to `v1`, which rejects the thinking and JSON settings | env `GENAI_API_VERSION` |

If the API rejects the thinking budget or JSON mode with a 400, the call is retried once without that setting and a
warning is logged. A model that doesn't support one of them still runs.

### Measured

One live check on November 13, 2026, with the real Part 1 prompt. The transcript was a made-up four-item test
meeting, because YouTube captions could not be reached from the session that ran it. It shows the mechanics. It does
not show analysis quality on real meetings, which still needs a side-by-side check on real transcripts
([#263](https://github.com/getcommunityone/open-navigator/issues/263)).

| Call | Input tokens | Cached input | Output tokens | Thinking tokens | Latency |
|---|---|---|---|---|---|
| `gemini-2.5-flash`, before | 9,401 | 0 | 10,266 | 10,668 | 82.0 s |
| `gemini-2.5-flash`, after | 9,399 | 0 | 10,166 | 0 | 42.0 s |
| `gemini-2.5-flash-lite`, after | 9,399 | 0 | 9,216 | 0 | 20.6 s |
| `gemini-2.5-flash-lite`, after, next meeting | 9,399 | 8,123 | 10,597 | 0 | 24.0 s |
| `gemini-2.5-flash`, after, next meeting | 9,399 | 8,123 | 11,658 | 0 | 48.0 s |

All five returned parseable JSON with the four decisions. On `gemini-2.5-flash`, billed output (output plus
thinking) fell from 20,934 tokens to 10,166, and the call took half as long.

## Running the backlog as a batch (#264)

Nothing needs a backlog answer within seconds. The Batch API takes the same requests as a file, answers within a
day and bills them at a discount, and no connection is held open per transcript.

```bash
# 1. Build the requests for pending transcripts and create the job(s)
python -m llm.gemini.batch_backlog submit --state AL
python -m llm.gemini.batch_backlog submit --state AL --limit 50 --dry-run   # write the files, create no job

# 2. See where the jobs are
python -m llm.gemini.batch_backlog status

# 3. Save the finished jobs' analyses
python -m llm.gemini.batch_backlog collect
python -m llm.gemini.batch_backlog collect --wait      # poll until every job has ended
```

A request is built by the same code as the interactive call (`prepare_part1_request`) and a response is saved by
the same code (`save_part1_response`), so both write the same analysis JSON, meta file and bronze stamps.

Each job has a folder under `data/cache/gemini_batch_jobs/` (`--jobs-dir`): `manifest.json`, the uploaded
`requests.jsonl`, one `requests/<video_id>.json` per video and the downloaded `results.jsonl`.

One live job ran end to end on November 13, 2026: three made-up test meetings on `gemini-2.5-flash-lite`, created,
finished in about two minutes and collected. All three analyses were saved with their token counts (28,200 input
and 31,620 output tokens in total), and a second `collect` rewrote nothing. The requests were built directly, not
selected from the warehouse, because the session had no database: `submit`'s selection of pending videos is covered
by the code it shares with the interactive pipeline, and has not been run against the warehouse yet.

Rules the runner keeps:

- A video in a job that has not ended, or has ended and not been collected, is not submitted again.
- A request that failed is stamped as a failed analysis and is picked up by the next `submit`.
- Collecting twice rewrites nothing: a video whose analysis exists is left as it is.
- More than `--max-requests-per-job` requests (default 500) are split across jobs.
- Each collected response is in the usage log with `api_mode = "batch"`.

Limits:

- A job belongs to the API key that created it. Run `status` and `collect` with the same `GEMINI_API_KEY` as
  `submit`. The key pool is not rotated.
- `--diarize` is not supported, because it needs a GPU at submit time.
- Part 2 (the Markdown report) is not run, as in `analyze_backlog`.

## Decisions

- **Thinking off by default.** The analysis is extraction against a fixed schema. The measured call spent as many
  tokens thinking as answering. The flag stays so a quality check can turn it back on for comparison.
- **JSON mode without a response schema.** The Part 1 schema is large and nested; sending it as a `response_schema`
  risks the API refusing it as too complex. JSON mode alone removes the fenced, free-text output. The prompt still
  carries the schema.
- **Implicit caching, not explicit caches.** Reordering the message is free and needs no cache to create, pay
  storage for or expire. An explicit cache is worth revisiting if the usage log shows a low cached share.
- **Batch jobs live beside the policy cache, not inside it.** The cache's migration and status tools walk its
  top-level folders as states and jurisdictions.
- **Local Gemma and DeepSeek were not changed.** Both are already wired in. Neither was measured as cheaper than
  Flash-Lite in batch mode, so nothing moves to them without numbers from the usage log.
- **Flash leads the backlog again.** The first comparison caught `gemini-2.5-flash-lite` recording a 5-2 vote as 2-5.
  One made-up meeting is thin evidence, but a wrong vote count shown to residents costs more than the saving, so the
  cheaper default waits for the comparison on real meetings (#267).

## Comparing models (#267)

`python -m llm.gemini.compare_models` sends the same Part 1 message to several models (*arms*) for meetings that
already have an analysis, and scores each answer against that analysis or against one arm. It writes `summary.md`
(scores, tokens, latency and cost per arm, then every missed item, added item and differing vote for a person to
check), `comparison.csv` and the raw answers under `data/cache/model_comparison/<run>/`. Nothing in the policy cache
changes.

```bash
python -m llm.gemini.compare_models --jurisdiction-id municipality_0177256 --state AL --limit 10
python -m llm.gemini.compare_models --rescore data/cache/model_comparison/<run>   # re-score, no model calls
```

The default arms are `gemini-2.5-flash` with and without thinking, `gemini-2.5-flash-lite`, the successors
`gemini-3.5-flash-lite` and `gemini-3.8-flash`, and the open-weights `gemma-4-26b-a4b-it` and `gemma-4-31b-it`
through the Gemini API. The scores measure agreement with the reference, not correctness.

### First run: one made-up meeting

Run on November 13, 2026 against the made-up four-item test meeting, with `gemini-2.5-flash` (thinking on) as the
reference. One meeting decides nothing; it shows what the tool catches.

| Arm | Items found | Votes agree | Places found | Thinking tokens | Latency | Cost per meeting |
|---|---|---|---|---|---|---|
| `gemini-2.5-flash` (reference, thinking on) | | | | 10,668 | 82 s | $0.055 |
| `gemini-2.5-flash`, thinking off | 4/4 | 4/4 | 0.8 | 0 | 42 s | $0.028 |
| `gemini-2.5-flash-lite` | 4/4 | **3/4** | 0.8 | 0 | 21 s | $0.005 |
| `gemini-3.5-flash-lite` | 4/4 | 4/4 | 0.6 | 0 | 17 s | $0.025 |
| `gemini-3.8-flash` | 4/4 | 4/4 | 0.8 | 2,097 | 81 s | $0.058 |
| `gemma-4-31b-it` | 4/4 | 4/4 | 0.8 | 2,050 | 288 s | no price |
| `gemma-4-26b-a4b-it` | 4/4 | 4/4 | 0.8 | 5,196 | 1,121 s, third try | no price |

Costs use the interactive list prices in `prices.yaml` (sourced from getdeploying.com, to be confirmed: #266).

What it showed:

- `gemini-2.5-flash-lite` recorded the rezoning vote as 2-5; the transcript says "The motion carries 5-2."
- Both Flash-Lite models placed every address in "Tuscaloosa, AL", copying the hard-coded jurisdiction line in the
  prompt (#265), where the transcript names Riverbend City. Flash got the city right. Fixing #265 matters most for
  the cheap models.
- `gemini-3.5-flash-lite` is not a cheap successor: its list price is the same as `gemini-2.5-flash`'s. Google is
  reported to have closed the 2.5 models to new users in July 2026 (see `prices.yaml`), so the cheapest option may
  not last.
- Gemma through the Gemini API is too slow for the backlog: the 31B model took almost five minutes per meeting, and
  the 26B model answered on its third try after almost 19 minutes, with its JSON wrapped in an array. Both
  answers were as good as Flash's on this meeting; the speed is the problem. At the pipeline's 300-second timeout both fail with "504
  DEADLINE_EXCEEDED", because the SDK forwards the client's timeout to Google as the server deadline. The tool
  raises its own timeout to 1,200 seconds for that reason.

## Where the output goes (#269)

`python -m llm.gemini.part1_field_sizes <answers or analysis files> [--count-tokens]` measures each field's share
of the output. Across the nine answers to the made-up meeting collected on November 13, 2026 (seven models):

| Field | Share of output | Read by |
|---|---|---|
| `decisions[]` as a whole | 82% | |
| `decisions[].competing_views` | 15% | dbt marts, API (`decisions`, `lenses`, search) |
| `decisions[].speaker_segments` | 12% | **nothing outside the prompt** |
| `decisions[].smart_brevity` | 10% | dbt, API, `DecisionDetail` page |
| `decisions[].evidence_metrics` | 9% | **nothing outside the prompt** |
| `decisions[].human_element` | 7% | dbt `decision_speakers`, API, `DecisionDetail` page |
| the two diagrams | 10% | Part 2 report, dbt |
| the two `*_lines` diagram helpers | 7% | only as a fallback when a diagram string is missing |

The helper lines were removed from the prompt as a test, three runs each on `gemini-2.5-flash-lite`: output averaged
8,713 tokens before and 8,918 after, within run-to-run noise, and one run lost a diagram it could no longer be rebuilt
from. The change was reverted. The model's output length doesn't shrink just because one optional field goes.

`speaker_segments` and `evidence_metrics` are about a fifth of the output and nothing reads them yet.

**Decision (November 13, 2026): keep both.** The maintainer chose to keep them in the Part 1 schema for the features
that will read them (per-speaker floor time, the figures cited as evidence; see CORE-2.2, #241), rather than save
their share of the output now. If this is revisited, measure on real meetings with `part1_field_sizes` first: the
helper-line test showed that removing a field does not by itself shorten the output.

## Not done

- Batch, Gemma and DeepSeek prices are not filled in, and the Gemini interactive prices still need confirming
  against Google's page (#266).
- The comparison has not run on real meetings (#267).
- Output is the larger half of every call: the made-up four-item meeting produced about 10,000 output tokens, much
  of it the two Mermaid diagrams the schema requires on every decision. Trimming the schema is the next lever and
  is a prompt change, not made here.
