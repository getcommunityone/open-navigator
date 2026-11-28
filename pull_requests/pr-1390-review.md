---
pr: 1390
branch: perf/1389-slim-speaker-serving
title: "perf(neon): slim speaker and comment serving tables, survive a served schema without attribution_tier"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude
verdict: approve
---

# PR Review: slim speaker and comment serving tables

## Summary

Public projections of `meeting_comment` and `meeting_speaker_position` keep only the rows and columns the API reads; `meeting_speaker_turn` (no reader) is unpublished; gold is unchanged. The API retries without `attribution_tier` when the served copy lacks it.

## Checks

- Readers found by grep: `topics.py` (meeting_comment, meeting_passage_speaker), `data_center_comments.py` and `data_center_drill.py` (meeting_speaker_position), `data_centers.py` (meeting_passage_speaker). No reader of `meeting_speaker_turn`.
- 25 endpoint responses are identical before and after slimming.
- Added serving size is about 2.7 MB of rows, under the 15 MB target.
- No private data added: names stay "First L."; minors are excluded from `meeting_comment`.
- No Neon write was made.

## Findings

None blocking. Nit: `tests/test_telemetry_db.py` fails on main too (not this change).
