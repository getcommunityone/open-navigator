{% macro ensure_search_indexes() %}
{#-
    Rebuild-proof the /search performance indexes.

    Each search-serving mart declares its indexes in its own model post_hook, but
    some rebuild paths skip post_hooks (the table is renamed in from
    <model>__dbt_tmp without the CREATE INDEX statements firing — the tell is a
    surviving `<model>__dbt_tmp_pkey` and NO other indexes). When that happens the
    index silently vanishes and the matching /search text leg degrades to a full
    sequential scan: ~18s for org name FTS over mdm_organization (~4.1M rows), ~19s
    for the un-indexed ILIKE over public.grant (~6.7M rows). Concurrently fanned
    out, one such leg drags the whole homepage /search past the frontend's 20s
    fetch-abort so NO category renders.

    This executes its work via run_query (NOT by rendering DDL as hook text), so it
    behaves identically whether fired from on-run-end after every `dbt run` or
    invoked directly as the self-heal runbook:

        dbt run-operation ensure_search_indexes

    CREATE INDEX IF NOT EXISTS is a cheap catalog check when the index already
    exists and only builds (non-CONCURRENTLY, matching the recreate runbook) when it
    is actually missing — steady-state runs pay almost nothing while a post-rebuild
    gap self-heals. Each table is guarded by to_regclass so a partial run / fresh
    warehouse that lacks a table is skipped, not errored.

    See api/routes/search_postgres.py (search_organizations_pg / search_grants_pg /
    search_persons_pg) and the *_index_drops notes.
-#}
{%- if not execute -%}{{ return('') }}{%- endif -%}

{%- set indexes = [
    {'rel': 'public.mdm_organization',  'name': 'mdm_organization_org_name_fts_idx',  'def': "using gin (to_tsvector('english', org_name))"},
    {'rel': 'public.mdm_organization',  'name': 'mdm_organization_org_name_norm_idx', 'def': '(org_name_norm)'},
    {'rel': 'public.mdm_organization',  'name': 'mdm_organization_state_code_idx',     'def': '(state_code)'},
    {'rel': 'public.mdm_person',        'name': 'mdm_person_full_name_trgm_idx',       'def': 'using gin (full_name gin_trgm_ops)'},
    {'rel': 'public.contact_official',  'name': 'contact_official_full_name_trgm_idx', 'def': 'using gin (full_name gin_trgm_ops)'},
    {'rel': 'public.contact_official',  'name': 'contact_official_title_trgm_idx',     'def': 'using gin (title gin_trgm_ops)'},
    {'rel': 'public."grant"',           'name': 'grant_grantor_name_trgm_idx',         'def': 'using gin (grantor_name gin_trgm_ops)'},
    {'rel': 'public."grant"',           'name': 'grant_grantee_name_trgm_idx',         'def': 'using gin (grantee_name gin_trgm_ops)'},
    {'rel': 'public."grant"',           'name': 'grant_purpose_trgm_idx',              'def': 'using gin (purpose gin_trgm_ops)'},
    {'rel': 'public.jurisdictions',     'name': 'jurisdictions_search_fts_idx',        'def': "using gin (to_tsvector('english', coalesce(search_text, display_name)))"}
] -%}

{%- do run_query("create extension if not exists pg_trgm") -%}

{%- set created = [] -%}
{%- set skipped = [] -%}
{%- for ix in indexes -%}
  {%- set check = run_query("select to_regclass('" ~ ix.rel ~ "') as r") -%}
  {%- if check and check.rows and check.rows[0][0] is not none -%}
    {%- set present = run_query("select to_regclass('public." ~ ix.name ~ "') as r") -%}
    {%- if not (present and present.rows and present.rows[0][0] is not none) -%}
      {%- do created.append(ix.name) -%}
    {%- endif -%}
    {%- do run_query("create index if not exists " ~ ix.name ~ " on " ~ ix.rel ~ " " ~ ix.def) -%}
  {%- else -%}
    {%- do skipped.append(ix.name) -%}
  {%- endif -%}
{%- endfor -%}

{{ log("ensure_search_indexes: built " ~ (created | length) ~ " missing index(es): " ~ (created | join(', ') if created else 'none') ~ (" | skipped (table absent): " ~ (skipped | join(', ')) if skipped else ''), info=true) }}
{%- do return('') -%}
{% endmacro %}
