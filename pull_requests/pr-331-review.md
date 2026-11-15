---
pr: 331
branch: fix/321-ntee-seed-committed
title: "fix(ingestion): commit the vendored NTEE seed, sourced from NCCS's code table"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(ingestion): commit the vendored NTEE seed, sourced from NCCS's code table

## Summary

The NTEE loader's documented offline fallback, `seed_ntee_codes.csv`, was never committed, because `*.csv` is
ignored. The PR commits it, rebuilt from NCCS's NTEE code table: the 26 major groups, each named as the table's own
descriptions name it, and Z from Z99's definition. It adds a one-file `.gitignore` exception, cites the source in the
module docstring, and removes the skip #305 put on the seed test. Closes #321. Approve.

## Scope of Change

- Files changed: 4: `.gitignore`, `codes.py` (docstring), `test_ntee_codes_pipeline.py` (skip removed), new
  `seed_ntee_codes.csv` (26 rows)
- Areas touched: packages (ingestion), repo config

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean. Every description is a verbatim phrase from NCCS's table, and the docstring says how each
  was taken. `ntee_type` is a label for the kind of row (`major group`), not a measured value.
- Personal data: none. These are public taxonomy codes.
- Destructive or bulky changes: none. The file is 1 KB.

## Findings

None blocking, none to fix, no nits. The seed's group names follow the table's most common wording (for example
"Health - General and Rehabilitative" for E). That's the table's own text, not a shorter popular label.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #321 has all four parts; `Closes #321` |
| Conventional Commits | Yes | `fix(ingestion): ...` with the co-author trailer |
| No fabricated data | Yes | Rows come from a named, dated public source |
| Tests | Yes | `test_extract_vendored_seed_is_loadable` runs again and passes (15 of 15 in the file); whole suite 1353 passed |

## Verdict

Approve once the required checks are green.
