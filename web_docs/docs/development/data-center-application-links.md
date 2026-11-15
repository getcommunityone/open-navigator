---
sidebar_position: 33
title: Data center application links
description: How admins keep job-application links for data center projects, and how each link's verification and 30-day staleness work (DC-1.3).
---

# Data center application links

Jobseekers asked for application links that still work. [DC-1.3](https://github.com/getcommunityone/open-navigator/issues/248)
lets admins keep those links, records when each one was last verified, and flags any link not verified in 30 days. It
is part of the [Data Center Accountability epic](https://github.com/getcommunityone/open-navigator/issues/236), next
to the [jobs claims](./data-center-jobs.md).

## In short

- Admins add links on **Admin → Application links** (`/admin/application-links`).
- Each link is **verified** when a check reaches the page, or when an admin opens it and clicks **Mark verified**.
- A link not verified in **30 days** is **stale**: flagged on the admin screen and on the public page.
- A link whose page is **gone** (HTTP 404 or 410) is hidden from the public page until it's fixed.

<details>
<summary>Where each piece lives</summary>

| Step | Where | What it does |
|---|---|---|
| Table | `public.job_application_link` (`api/models.py`, `JobApplicationLink`) | One row per application URL. PK `job_application_link_id`; FK `created_by_user_id` → `user`. Created at API startup by `Base.metadata.create_all`, like `user` |
| Check | `packages/ingestion/src/ingestion/data_centers/application_links.py` | `check_link(url)` requests the page (HEAD, then GET if HEAD is refused) and returns `live`, `dead` or `error`; `is_stale()` applies the 30-day rule |
| Batch check | `python -m ingestion.data_centers.verify_application_links [--limit N] [--dry-run]` | Checks links not checked in the last day and writes the results |
| Admin API | `/api/admin/application-links` (`require_admin`) | List (`?stale=true`), add, edit, delete, `/{id}/check`, `/{id}/verify` |
| Public API | `GET /api/data-centers/application-links?state=&city=` | The scope's links, without dead ones, each with `last_verified_at` and `is_stale` |
| Page | `/data-centers?state=&city=`, "Apply for jobs" | "Verified Nov 15, 2026", or "Not verified in the last 30 days" in amber |

</details>

<details>
<summary>Decisions and why</summary>

- **An admin screen, not a file or extraction** (owner's choice, November 15, 2026). Application links rarely appear in
  meeting records, and a screen lets an admin fix a link the moment it breaks.
- **App-owned table, not dbt.** People write to it; dbt models are rebuilt from sources. It follows the same pattern as
  `user` and `proximity_alerts`.
- **No foreign key to `jurisdictions` or `job_claim`.** dbt drops and rebuilds those relations, so a constraint would
  block the build or be lost. The place is carried as `state_code`, `state` and `city`, and the public list matches on
  them the way the jobs-claims route does.
- **Only 404 and 410 count as gone.** Careers sites often answer bots with 403, and timeouts happen. Those count as
  `error`: the link stays visible and isn't verified, so it turns stale after 30 days rather than vanishing.
- **A live page isn't proof the posting is open.** Many sites answer 200 with "this position is closed". The 30-day
  flag and **Mark verified** (an admin read the page) cover that.
- **Changing a link's URL clears its verification**, so a new URL starts stale until it's checked.

</details>

<details>
<summary>Running the batch check</summary>

It uses the API's database (`NEON_DATABASE_URL_DEV`, else `NEON_DATABASE_URL`, else `DATABASE_URL`):

```bash
python -m ingestion.data_centers.verify_application_links --dry-run   # check, write nothing
python -m ingestion.data_centers.verify_application_links --limit 100
```

Run it daily. A link checked in the last day is skipped.

</details>
