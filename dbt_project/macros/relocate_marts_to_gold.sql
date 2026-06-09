{% macro relocate_marts_to_gold() %}
{#-
    ONE-TIME migration: move the existing, already-built warehouse from `public`
    into the new `gold` schema WITHOUT a rebuild (sidesteps local build-gaps such
    as the missing bronze_jurisdictions). After this, dbt materializes marts into
    `gold` (see +schema: gold in dbt_project.yml) and publish_public_serving
    exposes ONLY the API-served relations back into `public` as thin views
    ("public = serving data and nothing else"; gold = the full/private set).

    Mechanics that make this safe:
      * Moves every base relation in `public` (relkind r=table, p=partitioned,
        v=view) EXCEPT the operational/ORM tables the API WRITES (kept in public).
      * ALTER TABLE ... SET SCHEMA does NOT move a partitioned table's children,
        so children (also relkind 'r') are enumerated and moved individually.
      * PK/FK/indexes/stored tsvectors travel with their table. Cross-schema FKs
        are by OID, so moving both endpoints in one transaction keeps them intact.
      * Executed as a SINGLE multi-statement run_query => atomic (all-or-nothing).

    Idempotent: it only ever moves what is still in `public`, so re-running after
    a completed migration is a no-op. Run once:

        dbt run-operation relocate_marts_to_gold
        dbt run-operation publish_public_serving   # then expose the served views

    Rollback is symmetric: ALTER ... SET SCHEMA public for the moved relations +
    DROP VIEW public.<served>. See the gold/public split plan.
-#}
{%- if not execute -%}{{ return('') }}{%- endif -%}

{#- Operational/ORM tables created by api/models.py Base.metadata.create_all.
    These are app-WRITTEN (auth, follows, user prefs) and must STAY in public. -#}
{%- set keep = [
    'user', 'contact_oauth_state', 'social_follows',
    'user_locations', 'user_lens_prefs', 'user_signal_prefs'
] -%}

{%- do run_query("create schema if not exists gold") -%}

{%- set rel_q -%}
  select c.relname, c.relkind
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind in ('r', 'p', 'v')
    and c.relname not in ('{{ keep | join("','") }}')
  -- partitioned parents first, then plain tables (incl. partition children), then views
  order by case c.relkind when 'p' then 0 when 'r' then 1 else 2 end, c.relname
{%- endset -%}
{%- set rels = run_query(rel_q) -%}

{%- if not (rels and rels.rows) -%}
  {{ log("relocate_marts_to_gold: nothing left in public to move (already migrated?)", info=true) }}
  {%- do return('') -%}
{%- endif -%}

{%- set stmts = [] -%}
{%- for row in rels.rows -%}
  {%- set relname = row[0] -%}
  {%- set kw = 'view' if row[1] == 'v' else 'table' -%}
  {%- do stmts.append('alter ' ~ kw ~ ' if exists public."' ~ relname ~ '" set schema gold') -%}
{%- endfor -%}

{#- Fail fast rather than block forever if a live backend holds a lock on a
    relation being moved (ALTER ... SET SCHEMA needs ACCESS EXCLUSIVE). -#}
{%- do run_query("set lock_timeout = '30s'") -%}
{%- do run_query(stmts | join(';\n')) -%}

{{ log("relocate_marts_to_gold: moved " ~ (stmts | length) ~ " relation(s) public -> gold (kept operational: " ~ (keep | join(', ')) ~ ")", info=true) }}
{%- do return('') -%}
{% endmacro %}
