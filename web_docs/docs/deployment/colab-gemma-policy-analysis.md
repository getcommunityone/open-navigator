---
title: Meeting policy analysis with Gemma on Colab
description: Run the meeting policy analysis (Part 1) with Gemma 4 31B on the owner's Colab GPU from transcripts exported on the laptop, compare it with the Gemini analyses, and load the results through the usual path.
---

# Meeting policy analysis with Gemma on Colab

**What it's for:** the meeting policy analysis (Part 1: decisions, votes, people, places, money) without the paid
Gemini API. It runs the **same** prompt (`prompts/policy_analysis_part_1.md`), the same output schema and the same
meta as `llm.gemini.meeting_transcript_policy`, but with Gemma 4 on the owner's Google Colab GPU, which uses prepaid
Colab compute units ([#511](https://github.com/getcommunityone/open-navigator/issues/511)). The first target is the
data center meetings since June that aren't analyzed yet
([#510](https://github.com/getcommunityone/open-navigator/issues/510)).

- **Model:** `google/gemma-4-31B-it` by default; `google/gemma-4-26B-A4B-it` (mixture of experts, about 4B active
  parameters) is the faster option.
- **Precision:** 4-bit (bitsandbytes NF4) when the GPU has under 70 GB, else bf16 (`--quantize auto`).
- **Decoding:** greedy (no sampling), so a rerun of the same meeting gives the same answer.

**A run uses the owner's Colab compute units.** It starts only on the owner's explicit yes for that run, the usage is
read before and after, and the cost goes in the run's issue or PR (`AGENTS.md`, "GPU and paid compute";
[GPU compute decisions](../development/gpu-compute-decisions.md)).

## How it fits together

| Step | Where | Module |
|---|---|---|
| 1. Export the Part 1 requests | laptop (local warehouse) | `python -m llm.gpu.colab_policy_export` |
| 2. Copy the bundle up | laptop → Drive or landing volume | Drive upload or `databricks fs cp` |
| 3. Run Gemma | Colab GPU | `notebooks/colab_gemma_policy_analysis.ipynb` → `llm.gpu.colab_policy_analyze` |
| 4. Copy the run folder down | Drive or volume → laptop | |
| 5. Pilot only: score against Gemini | laptop | `python -m llm.gemini.compare_models --rescore` |
| 6. Save into the policy cache | laptop | `python -m llm.gpu.colab_policy_import` |
| 7. Load and build | laptop | `promote_to_c1_event` → `load_analysis_cache_to_bronze` → dbt |

**Transcripts reach Colab without YouTube.** The export builds, for each meeting, the exact message the Gemini pipeline
would send (`prepare_part1_request`: prompt, MEDIA CONTEXT, speaker and agenda hints, official-record context), with
the transcript read from `bronze.bronze_event_youtube_transcript` only; a video whose transcript would have come from
anywhere else is skipped. Colab needs no database and no YouTube.

## 1. Export (laptop)

```bash
cd /home/developer/projects/open-navigator
export OPEN_NAVIGATOR_DATABASE_URL=...   # the local warehouse, localhost:5433/open_navigator
.venv/bin/python -m llm.gpu.colab_policy_export --data-center-since 2026-06-01 --pilot 3
```

- `--data-center-since` takes the videos in `public.data_center_meeting_mention` with a meeting date from that day to
  today that aren't in `public.event_meeting` yet. `--videos-file <file>` takes any list of video ids instead.
- `--pilot 3` adds three data center meetings that already have a Gemini analysis on disk, with that analysis as the
  reference.
- The database is `--database-url`, else `OPEN_NAVIGATOR_DATABASE_URL`, else `localhost:5433`. Neon URLs are never
  used.

The bundle is `data/cache/colab_gemma_export/<date>/`: `manifest.json` (prompt name, sha256 and version, each video's
transcript and prompt size, what was skipped and why), `videos.txt`, `pilot_videos.txt`,
`requests/<video_id>.json`, and `references/` for the pilot.

**The bundle from 2026-11-17:** 135 data center meetings (2026-06-01 to 2026-11-13), 3 pilot meetings, 142 MB. One
video was first skipped because `has_transcript` lagged its transcript row; the export now reads the row itself.
Prompts run from 40,000 to 952,000 characters (median 157,000); 9 are over 500,000. The longest probably won't fit
Gemma 4's context with room for the answer; the runner measures that with the real tokenizer and fails those clearly
rather than cutting the transcript (the Gemini pipeline doesn't chunk either).

## 2. Copy the bundle up

Either:

- **Drive:** upload the folder to `MyDrive/open-navigator/crawl/policy_export/<date>/` (the notebook mounts Drive
  when there are no Databricks secrets), or
- **Landing volume:**
  `databricks fs cp -r data/cache/colab_gemma_export/<date> dbfs:/Volumes/open_navigator/open_navigator_landing/crawl/policy_export/<date>`.

## 3. Run on Colab

Open
[`notebooks/colab_gemma_policy_analysis.ipynb`](https://colab.research.google.com/github/getcommunityone/open-navigator/blob/main/notebooks/colab_gemma_policy_analysis.ipynb)
signed in with the owner's Google account. **Runtime → Change runtime type → A100 GPU** (High-RAM). Then, in order:

1. **Check a GPU is attached.** It prints the GPU and its memory.
2. **Get the code.** Clones `main` and installs `transformers>=5.5`, `accelerate`, `bitsandbytes`.
3. **Secrets.** `HF_TOKEN`, a read token for an account that accepted the Gemma licence on the model page; optionally
   `DATABRICKS_HOST` and `DATABRICKS_TOKEN` (without them Drive is mounted). Values are never printed.
4. **Usage before.** Type the compute-unit balance and the CU/hour rate from Colab's **Resources** panel.
5. **Run.** Set `export_date`, `mode` (`pilot` or `full`), `model`, and tick **owner_said_yes_to_this_run** only after
   the owner has said yes to this run. Rerunning this cell after a disconnect skips meetings already done.
6. **Usage after.** Type the balance again. The measured compute units are recorded and apportioned to the meetings
   of this session by GPU seconds (labelled an estimate).
7. **Summary.** A table per meeting: status, items, tokens, attempts, seconds, compute units. Put it and the usage
   lines in the run's issue or PR.

The same run from a terminal on the GPU box:

```bash
python -m llm.gpu.colab_policy_analyze --videos-file policy_export/2026-11-17/videos.txt --pilot 3
python -m llm.gpu.colab_policy_analyze --videos-file policy_export/2026-11-17/videos.txt --limit 135
python -m llm.gpu.colab_policy_analyze --videos-file policy_export/2026-11-17/videos.txt --model gemma-4-26b-a4b-it
```

Flags: `--videos-file`, `--model`, `--quantize {auto,4bit,none}`, `--pilot N`, `--limit`, `--out` (default
`policy_analysis`), `--run-date` (to resume an earlier day's run), `--max-new-tokens` (default 32,768),
`--cu-per-hour`, `--dry-run` (plan only; no model).

### What a run writes

`crawl/policy_analysis/<run_date>/`:

| File | What |
|---|---|
| `<video_id>.analysis.json` | the validated answer (written last: its presence marks the meeting done) |
| `<video_id>.meta.json` | the pipeline's meta keys (`video_id`, `prompt_name`, `prompt_sha256`, `gemini_model`, `generated_at`, `usage`, `json_parsed`, `transcript`, ...) plus `prompt_version`, `model`, `backend: colab_hf`, `quantization`, `gpu_name`, `transformers_version`, `decoding`, `seconds`, `attempts`, `compute_units` |
| `<video_id>.response.txt` | the model's raw answer, which the import saves through the pipeline |
| `<video_id>.failed.json` | a meeting that failed: the reasons, the attempts, a short excerpt. No analysis is written |
| `meta.json` | the run: prompt version, and per session the model, precision, GPU, versions, decoding and counts |
| `usage.jsonl` | one row per meeting (model, backend, seconds, tokens, status, estimated CU); the measured batch CU and each meeting's share |
| `llm_usage/` | this session's `llm.usage` `gpu_runs` and `llm_calls` rows |
| `comparison/` | pilot only: a `compare_models` run folder (below) |

### Validation and repair

Every answer is checked against `llm.gemini.part1_schema`, typed models of the prompt's JSON Schema (the `meeting`
object, the `decisions` and `uncontested_items` arrays and the ids every row is keyed by, the vote and anchor
types). On 888 saved Gemini analyses it accepts 881; the 7 it rejects lack a `person_id` or a `headline`. An invalid
answer gets **one** repair turn: the errors, and "reply again with the corrected JSON object only". Still invalid
means failed. An answer that is valid but has no items is saved with the pipeline's `_error` (as the Gemini pipeline
does), so it stays off the site. Nothing partial or invented is ever written as a result.

## 4–5. Pilot: compare with Gemini

The pilot writes its meetings as one arm of a `llm.gemini.compare_models` run folder, `comparison/`: `run.json`
(reference `existing`), and per meeting `reference.json` (the Gemini analysis), `transcript.txt`, and
`<arm>.txt` + `<arm>.call.json`. The arm is named `google/gemma-4-31B-it@colab_hf-4bit`; a second pilot with the 26B
model adds a second arm in the same folder. Copy the run folder to the laptop and score it:

```bash
.venv/bin/python -m llm.gemini.compare_models --rescore data/cache/colab_gemma_runs/<run_date>/comparison
```

`summary.md` and `comparison.csv` then hold, per arm and meeting: items and decisions found against the reference
(recall, precision), vote agreement, people, places and dollar amounts, schema validity, **the share of quotes found
verbatim in the transcript** (for the arm and for the Gemini reference), tokens, seconds and compute units. Every item
missed or added, every vote that differs and every quote not in the transcript is listed for a person to check. These
are the same scores as every other model comparison, so the Gemma numbers sit next to past and future runs.

### Pilot results

Filled in after the owner's pilot.

| Model | Precision | GPU | Seconds per meeting | CU per meeting | Valid | Item recall | Decision recall | Quotes verbatim |
|---|---|---|---|---|---|---|---|---|
| `google/gemma-4-31B-it` | | | | | | | | |
| `google/gemma-4-26B-A4B-it` | | | | | | | | |

## 6–7. Import and load

```bash
.venv/bin/python -m llm.gpu.colab_policy_import --run data/cache/colab_gemma_runs/<run_date> \
    --bundle data/cache/colab_gemma_export/<date> --dry-run
.venv/bin/python -m llm.gpu.colab_policy_import --run data/cache/colab_gemma_runs/<run_date> \
    --bundle data/cache/colab_gemma_export/<date>
```

The import calls the pipeline's own `save_part1_response` with each raw answer, exactly as the Gemini Batch collect
does: the same normalisation, date check, legislation enrichment, `02_analysis` / `04_runs` layout and bronze stamps.
It skips pilot meetings (they have a Gemini analysis), meetings already analyzed in the cache, and anything not valid.

**The model is tracked to every decision.** The meta's `gemini_model` is the Gemma model, which
`load_analysis_cache_to_bronze` writes to `bronze_events_analysis_ai.ai_model` and dbt carries to
`event_decision.source_ai_model` (and `event_meeting.source_ai_model`). The column is `varchar(100)`, so
`google/gemma-4-31B-it` fits, and the bronze row is keyed on `(event_id, analysis_type, ai_model)`, so a Gemma row
never overwrites a Gemini one. Then the usual path: `python -m ingestion.youtube.promote_to_c1_event` →
`python -m llm.enrichment.load_analysis_cache_to_bronze` → dbt. What the Gemini path costs for the same work:
[transcript analysis cost](../development/transcript-analysis-cost.md).

## What wasn't measured before the first run

Everything here was built and tested without a GPU. Still unknown until the owner's pilot:

- **Download size and memory.** The 31B weights in bf16 are about 62 GB to download; 4-bit loading quantizes them in
  memory to roughly 18 GB plus the context's cache. An A100 40 GB should hold 31B in 4-bit with a 60,000-token
  prompt; an L4 (24 GB) is tight for 31B and better suited to the 26B model. bf16 31B needs an 80 GB GPU.
- **Seconds per meeting.** Not measured. A Part 1 answer is several thousand output tokens, and 4-bit generation is
  slower than bf16; expect minutes per meeting, not seconds.
- **The longest transcripts.** Whether they fit the context, and the memory a 200,000-token prompt needs.
- **4-bit and the mixture-of-experts model.** Whether bitsandbytes quantizes the 26B model's experts well.

## Later: the golden dataset and tracing

The pilot's comparison folder is the shape both follow-ups read:

- **Golden dataset ([#446](https://github.com/getcommunityone/open-navigator/issues/446)).** Once a person has
  checked a meeting's items, that checked analysis replaces `reference.json`, and the same `--rescore` scores every
  arm (Gemini, Gemma 31B, Gemma 26B) against it instead of against Gemini.
- **MLflow tracing ([#451](https://github.com/getcommunityone/open-navigator/issues/451)).** Each meeting's meta and
  usage row already carry what a trace needs (model, backend, precision, GPU, prompt version, decoding, tokens,
  seconds, compute units, status), so a trace per meeting can be logged from the run folder without changing the
  runner.
