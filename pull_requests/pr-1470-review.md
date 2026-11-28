---
pr: 1470
issue: 1436
branch: feat/1436-stance-coverage-topics
title: "feat(stance): speaker topics for the remaining town-meeting questions, gold set and cost estimate (#1436)"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1470 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1436-stance-coverage-topics`, `Closes #1436`; the issue has all four parts.
- **Scans:**
  - No secrets and no fabricated numbers. The doc's counts come from the free dry run and from the label files.
  - The gold file carries no speech: keys, labels, hashes, and notes of 14 words or fewer, checked for names by test and by a scan.
  - No data changes; the seed rows are appended, not seeded.
- **Privacy:**
  - The new topics ask only what a speaker argued on a local action. Clearing encampments is framed as a camping rule, not as anyone's housing status.
  - The minor and school-board exclusions in `SPEAKERS_SQL` are unchanged.
- **Paid compute:** nothing paid runs in this PR. The new topics are `HELD` (`--topic all` skips them, and a test asserts it). Gold scoring now caps spend and stops on 402. The estimate and commands wait for the owner's yes.
- **Pinned hashes:** the 19 existing topics are unchanged. The 11 new hashes are pinned as new entries.
- **AI-helper labels:** flagged in `labelled_by`, the doc and the PR body, as #1436 asks.
- **Checks:**
  - `packages/llm` pytest: 468 passed.
  - `tests/test_api_topics.py`: 14 passed.
  - ruff is clean.
- **Nits left:**
  - Seven new topics have under 8 clear items, so they can't pass yet; more labels are follow-up work.
  - Many sampled "public" passages are staff or council speech. The public-comment flag lets them through, and the classifier's off-topic answer drops them.
  - Seeding the new ids waits on #1401.

No blocking findings.
