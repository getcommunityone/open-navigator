---
sidebar_position: 38
title: Contact form privacy
description: Why the contact form no longer puts the sender's email in a public GitHub issue, where the email is kept, who can read it, and how long it is kept (#448).
---

# Contact form privacy

Decision for [#448](https://github.com/getcommunityone/open-navigator/issues/448), recorded 2026-11-16.

## In short

- The contact form still opens a GitHub issue, but the issue **no longer contains the sender's email**.
- The email is kept privately in the `contact_submission` table, in the API's own database.
- The issue says `Reply address kept privately (submission #<id>)`, so maintainers can look up the reply address.
- We plan to **clear the email after 180 days**. That is not automated yet ([#456](https://github.com/getcommunityone/open-navigator/issues/456)).

## Why the email left the issue

`POST /api/contact/submit` creates an issue in `getcommunityone/open-navigator`. That repository is public. The issue body
used to read `**From:** <name> (<email>)`, so every sender's email was published, indexed and open to scraping.
People who write to us did not agree to that. We still need a way to reply, so the email moved to a private store.

## Where the email is kept

The table is `contact_submission`, one row per accepted submission.

| Column | Type | Notes |
| --- | --- | --- |
| `contact_submission_id` | integer identity | Primary key. Shown in the issue. |
| `created_at` | timestamptz | When the form was sent. |
| `sender_name` | text | Also shown in the issue. |
| `sender_email` | text | Private. Nullable, so retention can clear it. |
| `subject` | text | Also shown in the issue title. |
| `github_issue_number` | integer, nullable | Set after the issue is created. |
| `github_issue_url` | text, nullable | Set after the issue is created. |

- It is a **runtime table**, like `user` and `contact_oauth_state`. The API creates it at startup with
  `Base.metadata.create_all` (`api/models.py`, `ContactSubmission`). dbt does not build it, and it has no foreign keys.
- The running API writes it to the database it signs users in with. In production that is the same database that holds
  `user`.
- The local-to-Neon serving sync **never copies it**. `hosting.neon.sync_public_to_neon` only copies objects on its
  `CIVIC_SERVING` allow-list, and `contact_submission` is also on its `RUNTIME_OWNED` deny-list. So a local copy can never
  reach Neon, and a sync can never overwrite the production rows.
- `make backup-public` leaves it out of snapshots (`PII_EXCLUDE_TABLES` in the `Makefile`).
- No API route reads it, and no `public` serving view selects from it.

## How a submission flows

1. The rate limit and duplicate check from [#409](https://github.com/getcommunityone/open-navigator/issues/409) run first.
   Rejected submissions are not stored.
2. The API saves the row, then creates the issue with the `submission #<id>` line.
3. When the issue is created, the API stores its number and URL on the row.
4. If GitHub fails, the API deletes the row. The user sees an error and can send again.
5. If the database is down, the issue is still created. It says `Reply address not kept (private store unavailable)`.
   The email is never put in the issue as a fallback, and the warning log does not contain it.

The message text itself is posted as written. If a sender types their email into the message, it will appear in the
issue. We do not scrub message text.

## Who can read it

Only people with credentials for the API's database: the maintainers who run the production API. There is no admin
screen for it yet. To reply, look up the row by the id in the issue:

```sql
SELECT sender_name, sender_email, subject, github_issue_url
FROM contact_submission
WHERE contact_submission_id = <id>;
```

## Retention

- Rule: clear `sender_email` (set it to `NULL`) 180 days after `created_at`. The rest of the row stays, so the issue link
  still works.
- 180 days is enough time to reply and follow up on any issue.
- **This is automated** ([#456](https://github.com/getcommunityone/open-navigator/issues/456)). The job is
  `python -m hosting.retention.contact_submission` (`packages/hosting/src/hosting/retention/contact_submission.py`).
  The `Contact form retention` workflow (`.github/workflows/contact-retention.yml`) runs it every Monday at 04:17 UTC
  against the API's database, using the repository secret `API_DATABASE_URL`. If that secret is missing the run
  warns and clears nothing, so the secret is part of keeping this promise.
- Check it with `python -m hosting.retention.contact_submission --dry-run`, which counts the rows it would clear and
  changes nothing. The output is a count, never an email.
- The job does exactly what this SQL does, so a maintainer can still run it by hand:

```sql
UPDATE contact_submission
SET sender_email = NULL
WHERE created_at < now() - interval '180 days'
  AND sender_email IS NOT NULL;
```

## Logs

The contact route and the Facebook data-deletion callback (`api/routes/data_deletion.py`) log no email addresses. The
deletion callback logs the internal `user_id` and the Facebook user id only. Database errors there log the error type,
not its text, because that text can include row values.
