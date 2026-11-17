---
sidebar_position: 1
title: How Open Navigator uses AI
description: Where Open Navigator uses language models, what "noise" in a model's context means, and how model runs are traced (the usage log today, MLflow next).
---

# How Open Navigator uses AI

Open Navigator uses language models to read public meeting records and pull out what was decided. Everything a model
produces that reaches the site has to trace back to the real record, with a verbatim quote as evidence
(`CLAUDE.md`, "No Fabricated Data"). This page says where models are used, explains one idea that comes up often,
**noise**, and describes how model runs are recorded and traced.

## In short

- **Gemini reads meeting transcripts** and writes the decisions, quotes, dollar amounts and speakers the site shows.
  It's the main use, and it's billed per call.
- **Jev screens transcripts** before Gemini, cheaply, to skip videos with nothing to analyze. It returns labels and
  probabilities, never text.
- **Noise** is anything in the model's input that doesn't help answer the question. It makes answers worse and costs
  money, so we work to keep it out.
- **Tracing** records what went into each model run and what came out. Today we record one usage row per model call
  and the prompt version. Full MLflow traces exist for the agents package, not yet for transcript analysis
  ([#451](https://github.com/getcommunityone/open-navigator/issues/451)).

## Where we use models

| Use | Model | What it produces | More |
|---|---|---|---|
| Transcript analysis | Gemini (flash-lite first, flash on failure) | Decisions, quotes, amounts, speakers, themes as JSON | [Transcript analysis cost](./transcript-analysis-cost.md) |
| Transcript screening | TypeSafe Jev | Meeting kind, "any decision?", "data center mentioned?" as probabilities | [Jev transcript screening](./jev-transcript-screening.md) |
| Alternative analysis provider | DeepSeek | Decisions and classifications with a lighter prompt; priced by time of day | `packages/llm/src/llm/usage/prices.yaml` |
| Policy questions | Sentence embeddings and clustering | Groups of similar decisions and questions | `packages/llm/src/llm/policy_questions/` |
| Speaker diarization, local generation | WhisperX, Gemma on a GPU | Who spoke when; local text generation | [GPU compute decisions](./gpu-compute-decisions.md) |
| Coding agents | Claude and others | Code changes, reviews | `AGENTS.md`, `CLAUDE.md` |

The prompt for transcript analysis is `prompts/policy_analysis_part_1.md`, versioned in git. Every analysis row records
which version of it was used (`prompt_version`, a hash of the prompt's text).

## What "noise" means

A model answers from what's in front of it: the prompt plus whatever we put with it (a transcript, a table, search
results). We call that its **context**. **Signal** is the part of the context that helps answer the question.
**Noise** is everything else.

Noise isn't harmless filler. A model spreads its attention over the whole input, so the more irrelevant text there is,
the more likely it is to miss the part that matters, mix up two similar things, or confidently use the wrong one.
And every word of noise is billed.

Examples from this project:

- **A long meeting with a short decision.** A three-hour council video where the vote on a rezoning takes ten
  minutes. The other 170 minutes (roll call, public comment on other items, a proclamation) are noise for the
  question "what did they decide about the rezoning?"
- **One big prompt for every meeting.** The analysis prompt is about 35 KB. A two-minute ribbon-cutting gets the same
  instructions as a budget hearing; most of them don't apply.
- **Two names that look alike.** `jurisdictions_count` counts Census geographies; `governments_count` counts local
  governments. Put both in front of a model without their definitions and it may use the wrong one. That's noise
  through ambiguity, sometimes called a clash.
- **Stale or raw data.** A table last rebuilt months ago, or a raw `bronze` table next to the cleaned `public` one,
  looks just as valid to a model as the right one.
- **Agents reading everything.** A coding agent that reads a large log or data dump instead of the schema fills its
  context with noise and has less room for what matters. That's why `CLAUDE.md` says to read schemas, not raw files.

How we reduce it:

- **Cut at units of meaning.** Transcripts are split at caption segments, not at an arbitrary character count.
- **Screen first.** Jev drops videos with no decision in them before the expensive model sees them.
- **Read the governed layer.** Models and the API read the `public` schema, not raw tables.
- **Say what each field means.** dbt schema files describe every column, so the definition travels with the data.
- **Say how fresh it is.** [Data freshness checks](./data-freshness.md) flag stale tables.

The six principles behind this are in [Context engineering](./context-engineering.md).

## Tracing model runs

A **trace** is the record of one run: what went in (which transcript, which chunks, which prompt version), which model
answered, how long each step took, how many tokens it used, and what came out. With traces you can answer "why did
the analysis of this meeting say that?" and compare two prompt versions on the same meetings, instead of judging by
reading outputs. A trace is made of **spans**, one per step, nested inside each other.

<details>
<summary>What we record today</summary>

| Record | Where | What it holds | What it doesn't |
|---|---|---|---|
| Usage log | `packages/llm/src/llm/usage/`, loaded into `bronze.bronze_llm_call` | One row per model call: model, API mode, token counts, latency, attempts, success, run ID, and labels (stage, video, jurisdiction). `python -m llm.usage.report` prices them | Inputs and outputs. By design only fixed labels can be logged, so a prompt or transcript never lands in it |
| Prompt version | `bronze.bronze_events_analysis_ai.prompt_version`, each analysis's meta file (`prompt_sha256`) | Which prompt text produced each analysis | Older analyses say `@unrecorded` |
| Jev screens | `bronze.bronze_transcript_screen_jev` | Each screen's answers, chunk counts, tokens and `question_version` | |
| MLflow traces | `packages/agents/agents/mlflow_base.py` | Spans per agent run and request (`mlflow.start_span`), LangChain autologging, for the Databricks agent classes | Not used by transcript analysis |

See [LLM usage tracking](./llm-usage-tracking.md) for the usage log.

</details>

<details>
<summary>What's next: MLflow traces for transcript analysis</summary>

MLflow 3.12 is installed and has a tracing API and Gemini autologging. The plan
([#451](https://github.com/getcommunityone/open-navigator/issues/451)):

- One trace per analyzed meeting, with spans for loading the transcript, screening it (Jev), the Gemini call (model,
  prompt version, tokens) and parsing and saving the result.
- The trace ID written to the analysis's meta file, so any row on the site can be traced back to its run.
- A local MLflow store by default (`MLFLOW_TRACKING_URI`), or Databricks when the run happens there.
- Scoring runs against a fixed set of checked meetings
  ([#446](https://github.com/getcommunityone/open-navigator/issues/446)), so a prompt or model change gets a number,
  not an opinion.
- No keys or credentials in traces. Transcripts are public records, but traces keep inputs to IDs and sizes unless a
  run opts in to full text.

</details>
