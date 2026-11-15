---
pr: 374
branch: docs/372-students-learning-path
title: "docs(students): add a students' learning path with code walkthroughs"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: docs(students): add a students' learning path with code walkthroughs

## Summary
Adds `web_docs/docs/for-students.md` (13 topics), a "Students" row and drill-down in the README, and a sidebar entry under Tutorials. The topics are: basic statistics, dbt, master data management (Splink), logistic regression, clustering, embeddings/RAG, LLMs, Databricks, MLOps, GitHub Actions, ontologies, data contracts and data products. Each gives the concept in plain words, code links, the reason it's built that way, and a command to try. Docs only.

## Checks made
- **Code claims verified against the files:**
  - minutes-lag median/p90/mean, the 0–180 day filter, `sample_n >= 5`;
  - peer-window percentile ranks and `ln(1+|x|)`;
  - Splink's five steps and sequential blocking;
  - HDBSCAN's noise label `-1`, the TF-IDF + SVD fallback, MiniLM mean pooling and L2 normalising, hash-skipping in `embed_instances`;
  - `ai_query` in the bronze model;
  - the CI jobs, the PR-conventions check, Databricks deploy skipping without secrets, the GPU workflow cap and cost rows;
  - the closure table and vocabulary seeds;
  - ODCS generator and ODPS product.
- **Logistic regression taught honestly:** the repo has no trained `LogisticRegression`. The section explains log-odds and the logistic function through Splink's match weights (`match_probability = 2^w / (1 + 2^w)`), says how that differs from a fitted model (unsupervised EM vs labelled fitting), and links #373 (`good first issue`) for a trained example.
- **Commands exist:** `python -m ingestion.mdm person --dry-run`, `python -m llm.policy_questions.run_pipeline`, `python -m llm.policy_questions.embed_instances`, `python -m llm.usage.report --by stage`, `python -m models.odcs --write`, the `dbt ls` / `dbt seed` selections. The SQL example's columns (`median_lag_days`, `p90_lag_days`, `sample_n`) exist.
- **Links:** every GitHub link resolves to a file in the repo, as do the doc-relative links and the README's relative links.

## Scans
Secrets, fabricated data, personal data, destructive changes: clean. The figures quoted (0–180 days, 5 samples, 12 months) come from the code.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Some "Try it" commands need the local warehouse or API keys; the page says so up front.

## Repo-Rule Compliance
Issue #372 (four parts), `Closes #372`, branch `docs/372-…`, doc in `web_docs/docs/` with front matter, Conventional Commits; the follow-up is filed as #373.

## Verdict
**approve.** Merge when CI is green.
