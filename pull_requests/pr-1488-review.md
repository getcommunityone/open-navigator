---
pr: 1488
branch: fix/1487-trending-serving-size
title: "fix(trends): keep the public trending serving data under 3 MB"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve
---

# PR Review: fix(trends): keep the public trending serving data under 3 MB

## Summary
This PR changes two config values and nothing else: served terms per sort go from 60 to 55, and evidence
`ts_headline` MaxWords goes from 22 to 20. The local rebuild measures 2.96 MB (1.11 MB of terms + 1.84 MB of
evidence), and the size test passes. Logic, columns and API are unchanged. Approve.

## Scope of Change
- Files changed: 4 (+5 / -5) plus this review
- Areas touched: dbt_project, web_docs
- Range reviewed: `origin/main..fix/1487-trending-serving-size`

## CI Status
| Check | Status |
|---|---|
| Required checks | see the PR (merge only when green) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four scans are clean.

## Strengths
- Small and measured, and the decision page's numbers are updated in the same PR.

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
| Issue first | Yes | #1487 |
| Conventional Commits | Yes | |
| Docs | Yes | Decision page sizes updated |
| Tests | Yes | `tests/test_trending_terms.py`: 12 passed locally, including the 3 MB check |

## Test Coverage
I ran `pytest tests/test_trending_terms.py` (12 passed) and `python -m models.odcs --check` (clean) after a dbt rebuild
of `trending_term` and `trending_term_evidence`.

## Verdict
Approve.
