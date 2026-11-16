-- Migration 112: a read-only role limited to the public serving schema
--
-- Until now every script, agent and the local API connected as the superuser, so
-- "read `public`, never `bronze` or `gold`" was a rule written in CLAUDE.md, not a
-- control (context-engineering.md, principle 2). `public_reader` makes it a
-- property of the data: members can read the public serving views and tables and
-- nothing else.
--
--   public_reader   NOLOGIN group role: USAGE on schema public, SELECT on its
--                   tables and views, now and for ones created later by the role
--                   that runs dbt (default privileges).
--
-- Logins join the group and get their password outside git, e.g.:
--
--   CREATE ROLE agent_reader LOGIN PASSWORD '<from your secret store>' IN ROLE public_reader;
--
-- A view in public reads gold with its owner's rights, so members need no grant
-- on gold. Nothing here changes existing roles. Undo with:
--
--   REASSIGN OWNED BY public_reader TO postgres; DROP OWNED BY public_reader; DROP ROLE public_reader;
--
-- Idempotent. Apply to the local warehouse and Neon dev only; never to production
-- without the owner's explicit yes for that run.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'public_reader') THEN
        CREATE ROLE public_reader NOLOGIN;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE open_navigator TO public_reader;
GRANT USAGE ON SCHEMA public TO public_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO public_reader;

-- Tables and views dbt creates in public later (run as the role that runs dbt).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO public_reader;

-- No access to the private layers, even if PUBLIC was ever granted something there.
REVOKE ALL ON SCHEMA bronze, staging, intermediate, gold, seeds FROM public_reader;
