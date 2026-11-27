---
pr: 1257
branch: fix/1201-topic-lean-live-sync
title: "fix(llm): main holds the topic_lean writer and dbt models that wrote the live topic readings"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: data-dbt-specialist subagent (read-only) and coordinator
verdict: approve
---

# PR Review: fix(llm): main holds the topic_lean writer and dbt models that wrote the live topic readings

## Summary
The PR puts on `main` the topic-lean writer and dbt models that wrote the live `bronze.bronze_transcript_topic_lean_jev` (16,894 rows). Until now they existed only uncommitted in the `on-tlean` worktree.
- **Hashes:** every topic's `question_version` computed from the branch equals the stored one, and the test suite pins them.
- **Columns:** `CREATE_SQL`, `UPSERT_SQL`, the dbt source and the live table each have the same 20 columns.
- **Dry runs:** they report 0 meetings to read for the four topics already fully read, and 587 for guns.
- **dbt:** the two affected models build and all 32 nodes pass.
- **Vitest:** the guard that was skipped now runs and passes.

The verdict is approve. The reviewer's one substantive finding (a dry run executed DDL) was fixed on the branch before this review was committed.

## Scope of Change
- Files changed: 13 (Python, dbt SQL/YAML, ODCS/ODPS contracts, one TS test plus a comment, one docs page, this review)
- Areas touched: packages (llm), dbt_project, web_app (test), web_docs
- Commits: 6e62b6e8 fix(llm): main holds the topic_lean writer and dbt models that wrote the live topic readings; follow-up fix(llm): topic lean dry run sends no DDL + this review
- Range reviewed: `origin/main...fix/1201-topic-lean-live-sync`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. No served constants were added. Row counts appear only in docs and tests, as provenance taken from read-only warehouse queries.
- **Personal data:** clean. The readings are per-meeting aggregates and nothing is tied to a person.
- **Destructive data changes:** clean. Bronze data is not modified. The mart was rebuilt through dbt.

## Strengths
- Hash equality is pinned in `STORED_QUESTION_VERSIONS`, so a rewording can't silently trigger a paid re-read of a whole topic.
- A test checks that the writer's columns, the dbt source and the staging model's reads stay in step (the failure in #1201).
- The `accepted_values` test that was failing (#1204) is replaced by tests on the rolled-up leans and on the raw five positions, so an out-of-set label still fails.
- The PR keeps main's guard that builds an empty relation until the table exists, and main's `distinct on (video_id)`, which prevents a PK fan-out.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None outstanding.
- Fixed on the branch: `topic_lean.run_topic` ran `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE` and a backfill `UPDATE` even with `--dry-run`. A dry run now only checks `to_regclass` and sends no DDL. With no table yet, it treats every meeting as unread. The dry run was re-run after the fix with the same counts.

### 🔵 Nits / suggestions (Minor)
- `stg_jev__transcript_topic_lean.sql`: the current version is the one screened most recently, so after a rewording the mart holds only the re-read subset until the re-read finishes. This is documented intent from #1126 and is not changed here.
- `test_topic_lean.py`: the imports are now sorted with ruff from the repo root (I001).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/1201-...`; `Closes #1201`, `Closes #1239`; both issues have the four parts; follow-up #1253 filed; #1214 referenced |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | `python -m llm.typesafe.screen_transcripts` |
| dbt for transformations | Yes | Fluoridation roll-up and outcome mapping are in the mart SQL |
| Naming | Yes | `state_code` and `state`; no dim/fact names |
| Keys | Yes | PK (video_id, topic_id); FKs to `civicsearch_topic` and `jurisdictions` |
| Calendar years | n/a | |
| Scope label / match evidence | n/a | No UI surface changed |
| Docs | Yes | `web_docs/docs/development/topic-meeting-lean.md` updated in the same PR |
| Telemetry and logging | Yes | loguru |
| Tests | Yes | Pinned hashes, column sync, `--topic all`, un-skipped vitest |
| Shared libraries | Yes | llm package tests (-k screen/typesafe/jev/topic: 55 passed) and API topic tests (49 passed) |

## Test Coverage
Run locally:
- `pytest packages/llm/tests/test_topic_lean.py`: 16 passed.
- llm `-k "screen or typesafe or jev or topic"`: 55 passed.
- API topic tests: 49 passed.
- `vitest topicPositions.test.ts`: 13 passed, 0 skipped. `tsc --noEmit` is clean.
- `dbt ls --select stg_jev__transcript_topic_lean+`: only the two models and their tests.
- `dbt build --select stg_jev__transcript_topic_lean topic_meeting_lean`: PASS=32.
- `models.odcs --check`: current.
- `--dry-run --topic all`: guns 587, every other topic 0.

## Verdict
Approve. Merge once the required CI checks are green.
