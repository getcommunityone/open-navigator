---
pr: 315
branch: feat/314-modal-gpu-diarize
title: "feat(llm): run the GPU transcription and speaker step on Modal, started from GitHub"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: feat(llm): run the GPU transcription and speaker step on Modal, started from GitHub

## Summary

Adds a Modal app that runs the existing WhisperX step on a T4, a GitHub workflow to start it, estimated-cost rows
and a per-run cap. The plain parts are tested (8) and the app builds; the GPU path is unverified until the first run.
Closes #314. Approve with one nit.

## Scans

Secrets: clean. Fabricated data: none. Costs are labelled estimates from Modal's published rate, dated; no transcript text is logged. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix.

Nit: whisperx is pinned only from below (as in requirements-transcript-diarize.txt); if the first run shows its API moved, pin it.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #314 with four parts, under epic #293 |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in packages/ | Yes | `llm.gpu`, run with modal run |

## Verdict

Approve once the required checks are green.
