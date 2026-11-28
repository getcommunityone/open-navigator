---
pr: 1493
issue: 1401
branch: fix/1401-curated-topics-seed
title: "fix(topics): align curated_topics seed with warehouse IDs 100001-100020 and 100101-100111"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve
---

# PR Review: fix(topics): align curated_topics seed with warehouse IDs 100001-100020 and 100101-100111

Reviewed against `.claude/review-rubric.md`.

## Summary

Reconciles `dbt_project/seeds/curated_topics.csv` with the live warehouse `seeds.curated_topics` IDs (`100001-100020` and `100901`, fixing `100007=violent-crime` and `100020=bike-lanes`) while preserving coverage topics `100101-100111` (`100111=battery-storage`), adds a contract test (`tests/test_curated_topics_seed.py`), rebuilds the stance/ranking marts with explicit selectors, and updates the development docs with the resulting counts.

## Scope of Change

- Files changed: 4 (+84 / -12)
- Areas touched: `dbt_project`, `tests`, `web_docs`
- Commits: `fca6ce61` (`fix(topics): align curated_topics seed with warehouse IDs 100001-100020 and 100101-100111 (#1401)`)
- Range reviewed: `main..HEAD`

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean (counts in docs match live Postgres `gold`/`public` queries).
- Personal data: clean (curated topic metadata and aggregate counts only).
- Destructive data changes: clean (`dbt seed` only updated `seeds.curated_topics` to the union of warehouse and branch rows; no data deleted).

## Strengths

- Keeps `100001-100020` and `100901` byte-for-byte consistent with the warehouse while retaining `100101-100111` so `battery-storage` now flows cleanly through `meeting_speaker_topic_side` and `topic_place_ranking`.
- Explicit dbt selectors avoided triggering the multi-hour `topic_transcript_link` rebuild.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts, branch/PR naming | Yes | #1401, `fix/1401-curated-topics-seed`, `Closes #1401` |
| Conventional Commits | Yes | `fix(topics): ...` |
| No fabricated data | Yes | Verified against live local warehouse |
| dbt for transformations | Yes | Seed + explicit dbt build + `publish_public_serving` |
| Docs with the change | Yes | `topic-place-rankings.md`, `speaker-stance-classifier.md` |
| Tests | Yes | `tests/test_curated_topics_seed.py` + `tests/test_topic_place_ranking_dbt.py` |

## Test Coverage

- `.venv/bin/ruff check tests/test_curated_topics_seed.py`: passed.
- `.venv/bin/pytest tests/test_curated_topics_seed.py tests/test_api_topics.py tests/test_topic_place_ranking_dbt.py tests/test_api_rankings.py packages/llm/tests/test_speaker_stance.py`: 49 passed, 1 skipped.
- `RUN_DBT_UNIT_TESTS=1 .venv/bin/pytest tests/test_topic_place_ranking_dbt.py`: 6 passed.
- `dbt seed` & explicit `dbt build`: PASS=38 WARN=0 ERROR=0.
- `cd web_docs && npm run build`: succeeded.

## Verdict

approve.
