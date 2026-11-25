{#
  #567: post_hook SQL that (re)attaches a PRIMARY KEY after a table rebuild.
  Promotes an existing unique non-partial index on the same columns when present
  (avoids a duplicate unique index from dbt `indexes:` config).
  Usage, AS A STRING so it renders when the hook runs, against the model's real relation:
         post_hook=["{{ gold_pk_post_hook('video_id') }}"]
         post_hook=["{{ gold_pk_post_hook('level, state_code, county, city') }}"]
  Called directly inside config() (post_hook=[gold_pk_post_hook(...)]) it renders at parse time,
  when {{ this }} still points at the default schema (public), not gold (#941).
#}
{% macro gold_pk_post_hook(col_list) %}
do $pk$
declare
  idx text;
  cols text[] := string_to_array(regexp_replace('{{ col_list }}', '\s+', '', 'g'), ',');
begin
  if exists (
    select 1 from pg_constraint
    where conrelid = '{{ this }}'::regclass and contype = 'p'
  ) then
    return;
  end if;

  select i.relname into idx
  from pg_index ix
  join pg_class i on i.oid = ix.indexrelid
  where ix.indrelid = '{{ this }}'::regclass
    and ix.indisunique
    and not ix.indisprimary
    and ix.indpred is null
    and (
      select array_agg(a.attname::text order by ord.ordinality)
      from unnest(ix.indkey) with ordinality as ord(attnum, ordinality)
      join pg_attribute a on a.attrelid = ix.indrelid and a.attnum = ord.attnum
    ) = cols
  limit 1;

  -- No constraint name: post_hooks run after dbt renames the old table to __dbt_backup, which
  -- still owns an index called <model>_pkey until it is dropped after COMMIT. A fixed name
  -- collides with it on every rebuild after the first (#941); Postgres picks a free one instead.
  if idx is not null then
    execute format('alter table {{ this }} add primary key using index %I', idx);
  else
    execute 'alter table {{ this }} add primary key ({{ col_list }})';
  end if;
end
$pk$
{% endmacro %}
