---
pr: 439
branch: feat/428-public-reader-role
title: "feat(hosting): add a public_reader role limited to the public serving schema"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review in a fresh worktree; each finding traced in the code)
verdict: approve-with-nits
---

# PR Review: feat(hosting): add a public_reader role limited to the public serving schema

## Summary
Adds migration 112, which creates a NOLOGIN `public_reader` group with USAGE and SELECT on `public` plus default
privileges for objects dbt creates later, and a docs page on creating a login. The design is right, and on a throwaway
Postgres a member reads public tables, a public view over `gold` and a table created after the migration, and is
refused `bronze` and `gold`. As written, though, the migration failed on any database not named `open_navigator` or
missing one of the five private schemas (a Neon copy holds only `public`), and a comment claimed the REVOKE removed
PUBLIC grants, which it can't. Both are fixed on the branch. The migration has still not been applied anywhere, as
the brief required. Approve with nits.

## Scope of Change
- Files changed: 2 (+94 / -0)
- Areas touched: packages (hosting migration) / web_docs
- Commits:
  - 791a3cc2 feat(hosting): add a public_reader role limited to the public serving schema
  - 517ef785 fix(hosting): let migration 112 run on any database and say PUBLIC grants still apply (review fix)
- Range reviewed: `fb865cc2..791a3cc2`, then the fix

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker changes) |

CI was read on 791a3cc2; the fix commit triggers a new run.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. The example passwords are `<from your secret store>` / `<password>` placeholders, and the reader
  URL goes in the gitignored `.env`.
- Fabricated data in a served path: clean.
- Personal data: clean.
- Destructive or bulky data changes: clean. The migration adds a role and grants, and changes no existing role. It's a
  warehouse change outside dbt, but roles and grants are not dbt's job, and the repo's migrations folder is where
  they belong.

## Strengths
- A group role plus per-tool logins, so one tool's login can be revoked alone.
- Default privileges, so the role keeps access after dbt rebuilds `public`.
- Undo steps and the "local and Neon dev only" rule in the file header.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Fixed (517ef785).** `112_create_public_reader_role.sql`: `GRANT CONNECT ON DATABASE open_navigator` and
   `REVOKE ALL ON SCHEMA bronze, staging, intermediate, gold, seeds` made the migration fail on a database with
   another name or without one of those schemas, though the header says to apply it to Neon dev too. Reproduced on a
   throwaway Postgres 16 in the session scratchpad (not the warehouse), in a database named `neondb`: the original
   stopped at line 33 with `database "open_navigator" does not exist`. Now `GRANT CONNECT` uses `current_database()`
   and the REVOKE loops over whichever of the five schemas exist. On the same instance the fixed file applied twice
   cleanly (idempotent). As a member login, `public.v` (a view over `gold`), `public.p` and a table created after the
   migration were readable, and `bronze.t` and `gold.g` failed with "permission denied for schema".
2. **Fixed (517ef785).** The comment "No access to the private layers, even if PUBLIC was ever granted something
   there" was wrong: a REVOKE from `public_reader` can't remove what members inherit from `PUBLIC`. The header and the
   docs' decisions now say so, with the `pg_namespace` query to check it. The PR body confirms PUBLIC had no schema
   access on 2026-11-16.
3. **Left (by design, owner action).** Issue #428's "Done when" includes "Applied locally and checked: a member reads
   `public` and is refused `bronze` and `gold`". It hasn't been applied, as the PR body says and as this review's
   brief required. The owner applies it to the local warehouse (and Neon dev if wanted) and runs the check in the docs
   page before or after merge.

### 🔵 Nits / suggestions (Minor)
1. **Left.** Default privileges cover objects created by the role that runs the migration (no `FOR ROLE`). The docs
   say to run it as the role that runs dbt; if dbt ever runs as a different role, add
   `ALTER DEFAULT PRIVILEGES FOR ROLE <dbt role> ...`.
2. **Left.** Nothing reads `OPEN_NAVIGATOR_READER_DATABASE_URL` yet. That's fine for this PR (the contract only names
   it), but switching agents and the MCP server to it is the follow-up that makes the role matter.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `feat/428-public-reader-role`; `Closes #428`; the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | |
| New Python in `packages/` | n/a | SQL migration in `packages/hosting/scripts/neon/migrations/`, the existing migrations folder |
| dbt for transformations | n/a | Roles and grants, not transformations |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | n/a | |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | `read-only-database-role.md`, kebab-case, frontmatter |
| Telemetry and logging | n/a | |
| Tests | Partial | No automated test; checked by hand on a throwaway Postgres (above) |
| Shared libraries | n/a | |

## Test Coverage
No automated test (migrations in this folder have none). Checked by hand on a throwaway Postgres 16 started in the
session scratchpad and removed afterwards: original and fixed migration, idempotency, member access and refusals, as
above. Migration number 112 is unique in the folder (111 has two files, from before this PR). The migration was not
applied to the warehouse or to Neon.

## Verdict
Approve with nits. The portability fix and the PUBLIC correction are in. It isn't done until the owner applies the
migration locally and runs the member check (#428's last "Done when" line).
