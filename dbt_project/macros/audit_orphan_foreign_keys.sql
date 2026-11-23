{% macro audit_orphan_foreign_keys(schema='gold', samples=3, show_clean=true) %}
{#-
    #786: read-only audit of columns that look like foreign keys but have none.

    A candidate is a `*_id` column in a `schema` table whose name and type match the
    single-column primary key of another table in the same schema, with no foreign key
    already joining them. For each candidate it counts child rows whose key has no row in
    the parent ("orphans") and prints a few sample values.

    It only runs SELECT queries. It never creates, changes or deletes anything. Run it by hand:

        dbt run-operation audit_orphan_foreign_keys
        dbt run-operation audit_orphan_foreign_keys --args '{schema: gold, samples: 5, show_clean: false}'

    Reading the result:
      - `0 orphans`: safe to declare as a `foreign_key` in `schema.yml`; `ensure_declared_foreign_keys`
        then adds it. Check first that the pair is a real relationship, not two tables that happen to
        share a column name.
      - `N orphans`: the child holds keys the parent lacks. Find why (parent not loaded yet, wrong key
        on the child, stale rows, or a gap that is expected) before declaring anything. This macro
        never decides that for you.
-#}
{%- if not execute -%}{{ return('') }}{%- endif -%}
{%- if target.type != 'postgres' -%}{{ return('') }}{%- endif -%}

{%- set candidates_sql -%}
    select child.relname::text as child,
           a.attname::text     as col,
           p.tbl::text         as parent,
           p.col::text         as parent_col
    from (
        select c.conrelid, cl.relname as tbl, pa.attname as col, pa.atttypid
        from pg_constraint c
        join pg_class cl on cl.oid = c.conrelid
        join pg_namespace n on n.oid = cl.relnamespace
        join pg_attribute pa on pa.attrelid = c.conrelid and pa.attnum = c.conkey[1]
        where c.contype = 'p'
          and array_length(c.conkey, 1) = 1
          and n.nspname = '{{ schema }}'
          and cl.relkind in ('r', 'p')
          and pa.attname like '%\_id'
    ) p
    join pg_class child on child.relkind in ('r', 'p') and child.oid <> p.conrelid
    join pg_namespace cn on cn.oid = child.relnamespace and cn.nspname = '{{ schema }}'
    join pg_attribute a
      on a.attrelid = child.oid
     and a.attname = p.col
     and a.atttypid = p.atttypid
     and a.attnum > 0
     and not a.attisdropped
    where not exists (
        select 1 from pg_constraint f
        where f.contype = 'f'
          and f.conrelid = child.oid
          and f.confrelid = p.conrelid
          and f.conkey = array[a.attnum]
    )
    order by 1, 2, 3
{%- endset -%}

{%- set candidates = run_query(candidates_sql) -%}
{%- set results = [] -%}

{%- for row in candidates.rows -%}
  {%- set child = row[0] -%}
  {%- set col = row[1] -%}
  {%- set parent = row[2] -%}
  {%- set pcol = row[3] -%}
  {%- set audit_sql -%}
      select count(*) as orphans,
             (array_agg(distinct c.{{ adapter.quote(col) }}::text))[1:{{ samples }}] as sample
      from {{ schema }}.{{ adapter.quote(child) }} c
      where c.{{ adapter.quote(col) }} is not null
        and not exists (
          select 1 from {{ schema }}.{{ adapter.quote(parent) }} p
          where p.{{ adapter.quote(pcol) }} = c.{{ adapter.quote(col) }}
        )
  {%- endset -%}
  {%- set r = run_query(audit_sql) -%}
  {%- do results.append({'child': child, 'col': col, 'parent': parent, 'pcol': pcol, 'orphans': r.rows[0][0] | int, 'sample': r.rows[0][1]}) -%}
{%- endfor -%}

{%- set with_orphans = results | selectattr('orphans', 'gt', 0) | sort(attribute='orphans', reverse=true) | list -%}
{%- set clean = results | selectattr('orphans', 'equalto', 0) | list -%}

{{ log('audit_orphan_foreign_keys (' ~ schema ~ '): ' ~ (results | length) ~ ' candidate key(s): ' ~ (with_orphans | length) ~ ' with orphans, ' ~ (clean | length) ~ ' clean. Read-only.', info=true) }}
{%- for r in with_orphans %}
{{ log('  ORPHANS ' ~ '%8s' % r.orphans ~ '  ' ~ schema ~ '.' ~ r.child ~ '.' ~ r.col ~ ' -> ' ~ r.parent ~ '.' ~ r.pcol ~ '   e.g. ' ~ (r.sample | string), info=true) }}
{%- endfor %}
{%- if show_clean %}
{%- for r in clean %}
{{ log('  clean   ' ~ '%8s' % 0 ~ '  ' ~ schema ~ '.' ~ r.child ~ '.' ~ r.col ~ ' -> ' ~ r.parent ~ '.' ~ r.pcol, info=true) }}
{%- endfor %}
{%- endif %}
{%- do return('') -%}
{% endmacro %}
