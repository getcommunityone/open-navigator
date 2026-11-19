---
pr: 582
branch: feat/456-contact-retention
title: "feat(hosting): clear contact-form senders' emails after 180 days"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: feat(hosting): clear contact-form senders' emails after 180 days

## Summary
The PR adds a package CLI, `python -m hosting.retention.contact_submission [--days 180] [--dry-run] [--database-url]`,
that sets `contact_submission.sender_email` to NULL on rows older than the cutoff and keeps the rest of the row. A
weekly GitHub workflow runs it against the API's database through the secret `API_DATABASE_URL`, and the privacy
page now says the retention is automated. The rule matches issue #456 exactly, the code is small and
parameterised, it never prints an email or credentials, and it runs from a clean environment holding only
`psycopg2-binary` and `loguru`, as the workflow does. I also ran the real `--dry-run` through psycopg2 against the
local PostgreSQL warehouse (0 rows, nothing changed). The production promise is not kept until the owner adds the
secret, and the PR says so. Three nits, no blocking or should-fix findings: approve-with-nits.

## Scope of Change
- Files changed: 5 (+269 / -2, no generated files)
- Areas touched: packages (hosting) / ci / web_docs
- Commits:
  - `f018eeae` feat(hosting): clear contact-form senders' emails after 180 days
  - `c4bc0a26` feat(hosting): schedule the contact-form retention job weekly
- Range reviewed: `0ba4fcd2..c4bc0a26` (base is `main`; the PR is not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | SUCCESS |
| Documentation Build (Docusaurus) | SUCCESS |
| Backend Tests (Python) | SUCCESS |
| API Types (OpenAPI -> TypeScript) | SUCCESS |
| PR conventions (linked issue) | SUCCESS |
| Detect Docker-relevant changes | SUCCESS |
| Docker Build Test (Full Stack) | SKIPPED (not required; no Docker files changed) |

The new workflow `Contact form retention` has not run yet (it triggers on a Monday cron and manual dispatch only).

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The workflow reads `${{ secrets.API_DATABASE_URL }}` and the code takes the URL from an
  argument or environment. No literal URL, password or token is in the diff or in this file. The URL is passed on
  the command line, which GitHub masks in logs. `describe_target` logs host, port and database only (test covers
  it).
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/src/` changed. The only numbers are
  the retention default (180, from the issue) and test fixtures.
- **Personal data:** clean, and this PR reduces it. It stores nothing, logs no email (the output is a count) and
  adds no personal data to the warehouse. The job runs only against the API's own database.
- **Destructive or bulky data changes:** the `UPDATE` is destructive by design and it is the requested behaviour:
  it nulls one column on rows older than the cutoff, with `sender_email IS NOT NULL` as a second guard. It touches
  no `data/cache/`, adds no large files and does not change the warehouse. It is a runtime table, outside dbt, as
  `ContactSubmission` documents. Not a finding. No dbt model changed, so `dbt ls` was not needed.

## Strengths
- Matches issue #456's Contract: same rule, the CLI path suggested there, `--days` and `--dry-run`, a count and
  never an email.
- A correct, parameterised query. The cutoff goes in as a bound parameter, `--days` is validated (>= 1) and the
  `f"...{where}"` fragment is a module constant, not user input.
- The database target is explicit and safe: a non-PostgreSQL URL is refused (exit 2), `postgres://` is normalised,
  a missing table gives a clear message (exit 1), and the log names host and database without credentials.
- New code is in `packages/hosting`, with loguru and a `python -m` entry point; nothing was added to `scripts/`.
- The workflow is least-privilege (`contents: read`), pinned to the real repository (`if: github.repository == ...`,
  so forks don't run it), defaults manual runs to a dry run, and skips cleanly when the secret is absent.
- The PR body is honest about what is unverified (the real `UPDATE` ran only in SQLite; the workflow has not run;
  the secret is missing).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **`.github/workflows/contact-retention.yml:30-36`: a missing secret gives a green run with only a warning.** A
   scheduled run that clears nothing looks the same in the Actions list as one that worked, so the 180-day promise
   could stay unkept with nobody noticing. *Verified by reading the gate step:* with `API_DATABASE_URL` empty,
   `run=false` and every later step is skipped, so the job ends successful. *Fix:* after the secret exists, change
   the gate to `exit 1` when `github.event_name == 'schedule'` (keep the warning for manual runs), so a lost or
   rotated secret turns the job red and notifies. Optionally also post the cleared count in the job summary.
2. **`web_docs/docs/development/contact-form-privacy.md`: "This is automated" is stated before it is true in
   production.** The same bullet does say the secret is required, so the doc is not wrong, but the "In short"
   section above still says "We plan to clear the email after 180 days. That is not automated yet (#456)". *Verified
   by reading the file:* the `## In short` bullet (line 16) was not updated and now contradicts the Retention
   section. *Fix:* update that bullet (for example "…cleared after 180 days by a weekly job, once the
   `API_DATABASE_URL` secret is set").
3. **`packages/hosting/tests/test_contact_retention.py`: the tests cannot see PostgreSQL-specific behaviour.** The
   rule runs in SQLite against `created_at TEXT`, so the `timestamptz` comparison, the `UndefinedTable` handler and
   `main`'s connect path have no test. I checked the first and last by hand, read-only: against the local
   warehouse `contact_submission.created_at` is `timestamp with time zone`, the cutoff string compared with a
   `timestamptz` correctly (`created_at < '2026-05-22 12:00:00+00:00'` counted only the older of two rows), and
   `--dry-run` ran end to end. *Fix (optional):* a test that fakes `psycopg2.connect` to cover the
   `UndefinedTable` and exit-code paths, or a Postgres-marked test where a database is available.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/456-contact-retention`; body says `Closes #456`; the issue has Problem, Done when, Contract and Read first. No Attributes table: #456 is an `action-item` follow-up, not planned PI work |
| Conventional Commits | Yes | Both commits `feat(hosting): …`, with the co-author trailer |
| No fabricated data | Yes | Scan above |
| New Python in `packages/` | Yes | `hosting.retention.contact_submission` is a `python -m` CLI; nothing in `scripts/` |
| dbt for transformations | n/a | A runtime, API-owned table; the `UPDATE` is a retention action, not a transformation, and the model docstring says dbt does not own the table |
| Naming | n/a | No models or columns added |
| Keys | n/a | No `public` model added; `contact_submission` keeps its PK and has no FKs by design |
| Calendar years | n/a | Only timestamps |
| Scope label matches filter | n/a | No UI |
| Match evidence on filtered tiles | n/a | No UI |
| Docs | Yes, with nit 2 | Existing page under `web_docs/docs/development/`; Docusaurus build passes |
| Telemetry and logging | Yes | loguru, no email or credentials logged. The OpenTelemetry rule is for FastAPI services; this is a CLI |
| Tests | Yes | New behaviour is covered; mutation check below |
| Shared libraries | Yes | `packages/hosting` tests run: 41 passed, 3 skipped |

## Test Coverage
- **Run locally** (in a worktree, with `PYTHONPATH` forced to the worktree's packages):
  - `pytest packages/hosting/tests`: 41 passed, 3 skipped. The 8 new tests pass.
  - `ruff check` on the new source and test files: clean.
  - Workflow YAML parses.
  - From a fresh venv with only `psycopg2-binary` and `loguru`, `PYTHONPATH=packages/hosting/src python -m
    hosting.retention.contact_submission --help` works, and a MySQL URL is refused with exit 2 and no credentials
    printed. This is the workflow's environment.
  - `--dry-run` through psycopg2 against the local warehouse (`localhost:5433/open_navigator`): connected, reported
    0 rows, wrote nothing (the read-only checks used a read-only session; the real `UPDATE` was not run on any
    PostgreSQL).
- **Mutation checks** (reverted with `git checkout` after each):
  - Dropping `AND sender_email IS NOT NULL`: 4 tests fail (the count changes).
  - Changing the comparison and nulling `subject` as well: 5 tests fail.
  - So the tests do catch a wrong predicate and a wide `UPDATE`.
- **Covered:** the 181/179-day boundary, only the email cleared, dry run, idempotence, `--days`, the exact cutoff,
  refusal of non-PostgreSQL URLs, and credential-free logging.
- **Not covered:** the PostgreSQL `UPDATE` itself, `UndefinedTable`, the missing-environment path (exit 2), and the
  workflow (not run yet). The PR body says the same.
- **Claims in the PR body:** the SQLite tests, the YAML parse and the local dry-run reproduce. "Workflow has not
  run" is true. The claim that the secret is missing is not something I can see (I cannot read repository
  secrets), so it is unverified.

## Verdict
**approve-with-nits.** Nothing blocks the merge. Before the privacy promise is true in production, the owner must
add the `API_DATABASE_URL` secret and run one manual dry-run dispatch; after that, nit 1 (fail scheduled runs when
the secret is missing) is worth doing, and nit 2 is a one-line doc fix. Nit 3 can wait.
