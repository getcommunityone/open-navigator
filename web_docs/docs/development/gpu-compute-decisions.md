---
sidebar_position: 31
title: GPU compute decisions
description: Where Open Navigator's GPU runs go, who approves a paid one, and how their cost is read.
---

# GPU compute decisions

Decided November 15, 2026, by the owner. Logged in [#357](https://github.com/getcommunityone/open-navigator/issues/357).

November 17, 2026: the owner confirmed that diarization (WhisperX) runs on Colab
([#297](https://github.com/getcommunityone/open-navigator/issues/297)); how to run it is in
[GPU speakers on Colab](../deployment/colab-gpu-diarize.md). A Modal workflow was built in the meantime
([GPU steps on Modal](../deployment/modal-gpu.md), #314). Its code stays, but runs don't go there.

## Context

Open Navigator's GPU steps (WhisperX diarization, local Gemma generation) are recorded one row per step
([LLM and GPU usage tracking](llm-usage-tracking.md), #262), and #297 moves the transcription and speaker steps to
Colab. The owner's Colab subscription is shared with health-transformation-lab-nlp. That project's Kaggle GPU pool went
from 60 hours to 17.73 left in two days of one week (its ADR 0007), much of it on runs that could not answer what they
were asked. Nothing in this repository said where a GPU run may go or who approves one.

## Decision

- Every GPU run goes to the owner's Colab, never the Kaggle account, which is kept for the competition work in
  health-transformation-lab-nlp.
- A paid GPU run starts only on the owner's explicit yes for that run.
- A run's usage is read before and after (the `gpu_run` rows and Colab's compute units) and its cost recorded in its
  issue or PR.
- Recorded outputs and CPU are tried first.

## Consequences

- Each GPU run waits for the owner's yes, and the owner opens the Colab session.
- Both projects' Colab spending is visible in their records, so one doesn't run the other short unnoticed.

## Revisit when

- The pipeline runs without the laptop (#293) and a GPU step must run on a schedule.
- A second funded GPU source exists.
