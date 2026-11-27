---
pr: 1287
issue: 1286
verdict: approve
---

# PR #1287 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `chore/1286-neon-comment-tables`, `Closes #1286`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data. The tables hold meeting public comments and speaker names already served on the live site; the change only adds names to an allow-list and moves no data.
- **Correctness:** five names added to `CIVIC_SERVING`, none already present or in `NON_SERVING`/`RUNTIME_OWNED`. Without them a full sync skips the tables as unclassified.
- **Size:** about 25 MB, prod projected 393 MB against the 480 MB budget; the sync's own size check still guards each run.
- **Verification:** `pytest packages/hosting` passes (49). No sync was run against Neon.
- **Docs:** `neon-serving-scope.md` has a line per table.

No blocking findings.
