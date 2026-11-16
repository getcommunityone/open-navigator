---
sidebar_position: 8
title: Read-only database role
description: The public_reader role that limits agents and read-only tools to the public serving schema, and how to set up a login.
---

# Read-only database role

Every script, agent and the local API used to connect as the superuser, so "read `public`, never `bronze` or `gold`"
was a rule in `CLAUDE.md`, not a control. Migration 112 adds a role that can read only the `public` serving schema.
It follows principle 2 of [Context engineering](./context-engineering.md): access rules belong to the data, not to a
prompt.

## In short

- **`public_reader`** is a group role with no login. It can read every table and view in `public`, including ones dbt
  creates later, and nothing in `bronze`, `staging`, `intermediate`, `gold` or `seeds`.
- **Logins join the group.** Their passwords stay out of git.
- **Use a reader login for anything that only reads served data:** agents, MCP tools, notebooks, and the public API
  once it's switched over. Pipelines that write (`dbt`, loaders) keep their own login.
- **Local warehouse and Neon dev only.** Never apply to production without the owner's explicit yes for that run.

<details>
<summary>Set it up</summary>

```bash
# 1. The group role (idempotent)
psql -h localhost -p 5433 -U postgres open_navigator \
  -f packages/hosting/scripts/neon/migrations/112_create_public_reader_role.sql

# 2. A login in the group, with a password you generate
psql -h localhost -p 5433 -U postgres open_navigator \
  -c "CREATE ROLE agent_reader LOGIN PASSWORD '<password>' IN ROLE public_reader;"

# 3. Keep the URL in .env (gitignored)
OPEN_NAVIGATOR_READER_DATABASE_URL=postgresql://agent_reader:<password>@localhost:5433/open_navigator
```

Check it: as `agent_reader`, `SELECT 1 FROM public.jurisdictions LIMIT 1` works and `SELECT 1 FROM bronze.bronze_event_youtube LIMIT 1` fails with "permission denied for schema bronze".

</details>

<details>
<summary>Decisions and why</summary>

- **A group role plus logins.** Each tool gets its own login, so one can be revoked without touching the others, and
  the grants live in one place.
- **Default privileges.** dbt rebuilds tables and views in `public`; default privileges grant `SELECT` on each new one,
  so the role doesn't lose access after a build. Run the migration as the role that runs dbt.
- **No grant on `gold`.** A view in `public` reads `gold` with its owner's rights, so readers see what the view exposes
  (including the PII-light projections) and nothing more.

</details>
