---
sidebar_position: 30
title: LLM and GPU usage tracking
description: How every model call and GPU step is recorded, and how to read the numbers.
---

# LLM and GPU usage tracking

Every model call and every GPU step writes one usage row, so a model, prompt or batching choice can be compared on
measured numbers. The work is logged in [#262](https://github.com/getcommunityone/open-navigator/issues/262). The
code is `packages/llm/src/llm/usage/`.

## What is recorded

| Record | One row per | Written by | What it holds |
|---|---|---|---|
| Model call | call, after its retries | `call_gemini_text` (Gemini and DeepSeek), the local Gemma backend | input, cached input, output and thinking tokens; latency including retries; attempts; outcome |
| GPU step | step wrapped in `gpu_run(...)` | WhisperX diarization, a local Gemma generation | wall time, GPU count and name, GPU-hours, mean utilization, peak memory, energy |

A failed call is recorded too, because its latency and attempts are what the retries cost. A count the API does not
report is stored as null. It is never estimated.

Rows are appended to JSON-lines files under `LLM_USAGE_LOG_DIR` (default `data/logs/llm_usage/`):

- `llm_calls_YYYYMMDD.jsonl`
- `gpu_runs_YYYYMMDD.jsonl`
- `gpu_samples/<gpu_run_id>.csv`, the raw `nvidia-smi` samples for one step

The transcript pipeline also stores each Part 1 call's numbers in the meeting's `*.meta.json`, under `usage`.

Set `LLM_USAGE_LOG=0` to turn recording off. A recording failure is logged as a warning and never stops a run.

## Labelling calls

A caller labels the calls it makes with `llm_call_context`. Only `stage`, `video_id`, `jurisdiction_id` and
`api_mode` are kept, so a prompt or transcript cannot reach the log by accident.

```python
from llm.usage.calls import llm_call_context

with llm_call_context(stage="part1", video_id=video_id, jurisdiction_id=jurisdiction_id):
    result = call_gemini_text(...)
result.usage.thinking_token_count
```

A GPU step is wrapped the same way. On a machine with no `nvidia-smi`, or with `device="cpu"`, it records nothing.

```python
from llm.usage.gpu import gpu_run

with gpu_run("whisperx_diarization", device=args.device, video_id=video_id):
    diarize_audio_whisperx(...)
```

## Reading the numbers

```bash
python -m llm.usage.report                      # by day, model and API mode
python -m llm.usage.report --since 2026-11-01 --by stage
python -m llm.usage.report --json
```

To query them in Postgres, load the logs. The loader applies migration `111_create_bronze_llm_usage.sql` if the
tables are missing, and a re-run adds only new rows.

```bash
python -m llm.usage.load_bronze --dry-run
python -m llm.usage.load_bronze
```

| Table | Grain | Primary key |
|---|---|---|
| `bronze.bronze_llm_call` | one model call | `llm_call_id` |
| `bronze.bronze_gpu_run` | one GPU step | `gpu_run_id` |

## Cost

Cost is not stored. The report multiplies the token counts and GPU-hours by the prices in
`packages/llm/src/llm/usage/prices.yaml`, so a corrected price reprices all history.

A price is used only when it has a value, a `source` and a `read_date`. Anything else shows as a dash. The Gemini
and DeepSeek rates are not filled in yet: fill them from each vendor's pricing page, with the page's URL and the date
you read it. The GPU prices are estimates of what the GPU time would rent for on a cloud (a Colab or Kaggle GPU is
paid in compute units or not at all).

## Decision: the same method as health-transformation-lab-nlp

The method follows the health-transformation-lab-nlp project, so the two projects' numbers can be read the same
way: token counts taken from the API's own response, an `nvidia-smi` loop sampled to a CSV, GPU-hours as session
time by GPU count, and a prices file where every price carries its source and the date it was read.

Two things differ, on purpose:

- **Where the rows go.** That project puts token counts on OpenTelemetry spans. Here the pipelines are standalone
  package CLIs, which this repository logs with loguru (`CLAUDE.md`), so the rows go to JSON-lines files and a bronze
  table. OpenTelemetry stays for the FastAPI service.
- **Cost is derived, not stored.** That project stores an estimated cost on each run. Here the report computes it,
  so no row holds a cost computed from a price that was later corrected.

## Not covered yet

The governance (Colab) pipeline calls the Gemini API directly in `gatekeeper_triage.py` and
`governance_meeting_llm.py` and does not go through `call_gemini_text`, so those calls are not recorded.
