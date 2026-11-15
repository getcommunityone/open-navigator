---
pr: 371
branch: docs/370-dataops-walkthrough
title: "docs(dataops): add a DataOps walkthrough to the README with links to the code"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: docs(dataops): add a DataOps walkthrough to the README with links to the code

## Summary
Adds `web_docs/docs/development/dataops-walkthrough.md` and a matching README row and drill-down for data platform and DataOps readers. It covers failure classification and retry, stuck-run recovery, safe reruns, data quality and contracts, AI in production, observability, and engineering standards, plus two real November 2026 incidents and a "Not built yet" list. It's docs only.

## Checks made
- **Every claim traced to code or a merged PR**, for example:
  - retry statuses and `max_attempts=5` with jitter: `core_lib/http/client.py`;
  - the four Gemini give-up types and retry-delay parsing: `genai_text_client.py`;
  - `BATCH_JOB_INACTIVITY_SECONDS` default 3600, minimum 60, `stale_cancel_reason`, units marked failed with exit code -1: `batch_job_status.py`;
  - SHA-256-only deletion, `skipped_collision`, dry-run claims: `transcript_cache_paths.py` (#215);
  - usage fields and "never guessed": `llm/usage/calls.py`;
  - `--repair` / `--strict`: `validate_mermaid_reports.py`;
  - no model call on empty text: `meeting_gap_analysis.py`;
  - exclusions to `05_exceptions/`: `policy_exclusions.py`.
- **Incident figures** come from #48 (about 1,000 moves per run) and the container log behind #367.
- **Links:** every relative link in the README resolves to a file. The doc page uses full GitHub URLs, like `code-walkthrough.md`. Sibling doc links exist. The page is added to the Tutorials sidebar next to the code walkthrough.
- **Gaps stated plainly:** no paging, no downstream notification, no learned anomaly detection, no AI root-cause assessment, no per-connection health checks.

## Scans
Secrets, fabricated data, personal data, destructive changes: clean. The only figures (5 attempts, 3,600 s, ~1,000 moves) are from code or #48.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `main` links will drift as files change. They match the existing walkthrough's convention.

## Repo-Rule Compliance
Issue #370 (four parts), `Closes #370`, branch `docs/370-…`, doc in `web_docs/docs/` with kebab-case name and front matter, Conventional Commits.

## Verdict
**approve.** Merge when CI is green.
