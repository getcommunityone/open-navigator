---
pr: 1038
issue: 1035
verdict: approve
---

# PR #1038 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1035-agenda-anchor-dates`, `Closes #1035`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data, no personal data, no deletions. The staging change is a view; no bronze rows
  are rewritten.
- **Correctness:**
  - A parsed date is kept only when its year equals the manifest year, so a file name naming another year (a 2019 plan
    crawled in 2026) stays undated rather than getting a wrong date.
  - `safe_date_from_parts` checks the month and day range against the month's length before calling `make_date`, so Feb 30
    returns null instead of failing the build.
  - Rows that already had a full date keep their original `meeting_date_source`; only `manifest_year_only` rows are
    re-read.
  - The doctext select uses `EXISTS` on staging by `(jurisdiction_id, url_sha256)`, so it can't fan out rows.
- **Checks:** scrapers tests pass locally; ruff is clean. Required CI runs on the PR.
- **Docs:** `data-center-agenda-items.md` updated.

No blocking findings.
