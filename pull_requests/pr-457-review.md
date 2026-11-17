# Review: PR #457 — fix(api): keep contact-form emails private (#448)

**Verdict:** approve · 🔴 0 · 🟡 0 · 🔵 2

## Scope
`api/models.py`, `api/routes/contact.py`, `api/routes/data_deletion.py`, `sync_public_to_neon.py` (deny-list),
`Makefile` (`PII_EXCLUDE_TABLES`), tests, decision page `contact-form-privacy.md`.

## Scans
- Secrets: none (`"fb_secret_key"` is a test fixture value).
- Fabricated data in a served path: none.
- Personal data: the change removes the sender's email from the public issue body and the deletion log; the email is
  stored only in the runtime-owned `contact_submission` table, excluded from the Neon sync and from `backup-public`.
- Destructive data changes: none (new table via `create_all`; a row is deleted only when its own issue failed).

## Checks
- `pytest tests/test_api_oauth_and_contact.py packages/hosting/tests`: 44 passed, 3 skipped.
- CI on the head commit: Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions pass; Docker skipped.

## Verified
- `submission_id` is assigned before the `try`, so the `finally` cleanup can't raise `NameError`; `_save_submission`
  catches its own errors, and a DB outage still creates an email-free issue.
- The #410 duplicate marker / rate limit order is unchanged; on any non-201 the marker is released and the stored row
  is discarded.
- No log line in `contact.py` or `data_deletion.py` contains an email; DB error logs show only the exception type.

## Nits (🔵)
1. In production the API database is the production Neon database, so `contact_submission` lives beside `user`.
   The owner accepted this (2026-11-16); the decision page says so.
2. Retention (clear `sender_email` after 180 days) is manual until #456.
