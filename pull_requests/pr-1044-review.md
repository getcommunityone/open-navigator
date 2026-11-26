---
pr: 1044
issue: 1043
verdict: approve
---

# PR #1044 review

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
