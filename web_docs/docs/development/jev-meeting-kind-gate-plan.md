---
sidebar_position: 34
title: Plan — Jev meeting-kind gate
description: Implementation plan for #658 (calibrate + --skip-jev-meeting-below).
---

# Jev meeting-kind gate — implementation plan

> **For agentic workers:** execute task-by-task with TDD. Spec:
> [jev-meeting-kind-gate.md](./jev-meeting-kind-gate.md). Issue #658.

**Goal:** Calibrate `P(government_meeting)` and opt-in skip non-meetings before Gemini.

**Architecture:** Mirror existing `jev_skip_video_ids` / `--skip-jev-below`. Add
`jev_skip_meeting_video_ids` + `--skip-jev-meeting-below`. Add `--calibrate` on
`screen_transcripts` (no Jev calls). Union skip sets when both flags set.

**Tech stack:** Python, psycopg2, argparse, pytest in `packages/llm`.

## Global constraints

- Unscreened / null probability / old `question_version` never skipped.
- Neither flag on by default.
- No transcript mutation; no dashboard work; no pre-caption filters.
- Docs live under `web_docs/docs/development/`; Conventional Commits; branch
  `feat/658-…`.

## Files

- Modify: `packages/llm/src/llm/typesafe/screen_transcripts.py`
- Modify: `packages/llm/src/llm/gemini/batch_backlog.py`
- Modify: `packages/llm/tests/test_typesafe.py`
- Modify: `web_docs/docs/development/jev-transcript-screening.md`
- Modify: `web_docs/docs/development/jev-meeting-kind-gate.md` (usage snippets)

### Task 1: Meeting-kind skip set + submit flag

- [x] Failing tests for parse flag, skip SQL semantics (current version, null excluded), union with decisions skip
- [x] `jev_skip_meeting_video_ids(database_url, min_meeting_p) -> set[str]`
- [x] `batch_backlog` `--skip-jev-meeting-below`; merge into `jev_skip` with distinct log lines
- [x] Tests pass; commit

### Task 2: `--calibrate`

- [x] Failing test for threshold table over fixture probs
- [x] `--calibrate` path: join screens to `policy_analysis_at IS NOT NULL`; print keep/skip at 0.5/0.6/0.7
- [x] Tests pass; commit

### Task 3: Docs + PR

- [x] Update screening + gate docs with flag/calibrate usage
- [ ] PR closes #658
