---
pr: 1461
issue: 1437
branch: feat/1437-topic-place-ranking
title: "feat(rankings): topic_place_ranking mart and /api/rankings (#1437)"
reviewed_at: 2026-11-28
reviewer: data-dbt-specialist subagent (read-only), findings verified by the coordinator
verdict: approve-with-nits
---

# PR #1461 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1437-topic-place-ranking`, `Closes #1437`; the issue has all four parts. The follow-up for the officials' marker is #1460.
- **Scans:**
  - No secrets, no fabricated numbers, and no personal data. The mart serves counts per place; the person key exists only inside the model.
  - School districts and possible minors are excluded.
  - No data deletion.
- **Correctness, traced:**
  - Each speaker counts once on their majority side; a tie becomes `split` with no side.
  - The window is `> as_of - 24 months` and `<= as_of`.
  - Shrinkage is `(a + 10·national)/(f + a + 10)`, with national taken over all non-school places' residents.
  - A place is ranked at ≥10 sided speakers and ≥2 meetings.
  - Band rank is partitioned by topic and band.
  - Officials are excluded from resident counts and meetings.
  - Warehouse checks: 696 rows, 65 ranked, 0 ranked rows under the minimum, 0 school-district rows, and 0 rows with more sided speakers than distinct meeting speakers.
- **Keys:** PK (jurisdiction_id, topic_id, window_months) with FKs to jurisdictions and civicsearch_topic, contract enforced.
- **Fixed in review:**
  - The digit topic id is matched with `[0-9]{1,9}`, so an oversized or Unicode digit falls back to the slug: 404, not 500 or 503. A test was added.
  - `check=False` on the opt-in dbt subprocess (ruff PLW1510).
  - `national` is documented as the in-scope summary under a band/state filter. The page labels it by the active filter ("Median of these places").
- **Nits left:**
  - A "First L." name that is roster-matched in one meeting and not another becomes two people, one resident and one official. This is rare and errs toward keeping officials apart.
  - `is_ranked` in the band-rank partition is redundant.
  - The doc's national table is a dated snapshot.
- **Checks:**
  - `pytest tests/test_api_rankings.py tests/test_topic_place_ranking_dbt.py`: 13 passed, 1 skipped (opt-in dbt run).
  - `dbt build --select topic_place_ranking`: PASS=15, including the unit test.
  - Ruff is clean.
  - Endpoints were smoke-tested against the local warehouse.

No blocking findings.
