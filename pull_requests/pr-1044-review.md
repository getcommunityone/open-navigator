---
pr: 1044
branch: fix/1043-company-search-term
title: "fix(web_app): a company's meeting count searches the brand actually said (Vrbo)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: cea0b68af2ea475ca8ffbb7fb0665e8c11724538
verdict: approve
---

# PR Review: fix(web_app): a company's meeting count searches the brand actually said (Vrbo)

## Summary

Automated review (#648) for PR #1044 on `fix/1043-company-search-term`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/companySearchTerm.test.ts`
- `web_app/src/utils/companySearchTerm.ts`
- `web_docs/docs/development/short-term-rental-companies.md`

## CI Status

See the PR checks on `cea0b68af2ea`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**

## Agent review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1043-company-search-term`, `Closes #1043`; the issue has all four parts. Contract note: with no
  quote the company has no mentions (the count is 0 and no link is drawn), so the fallback is the company name rather than
  a "most used alias", which the API doesn't return.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:** the `<mark>` text comes from the server's `ts_headline`, so it is a word the record matched; the regex
  reads only the first mark and the result is URL-encoded. The link is only rendered when the count is above 0.
- **Checks:** vitest and tsc pass; CI runs on the PR.
- **Docs:** `short-term-rental-companies.md` updated.

No blocking findings.
