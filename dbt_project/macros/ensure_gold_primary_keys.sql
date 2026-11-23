{#
  #567: attach PRIMARY KEY constraints on the 16 gold tables that lacked them.

  Prefer PRIMARY KEY USING INDEX when a unique non-partial index already exists
  on exactly those columns. Composite grains that used NULL for "not applicable"
  (jurisdiction_state_aggregate) must coalesce to empty string in the model
  before this macro can attach a PK — Postgres PRIMARY KEY columns are NOT NULL.
#}
{% macro ensure_gold_primary_keys(dry_run=true) %}
  {% set specs = [
    {'table': 'events_text_search', 'cols': ['video_id']},
    {'table': 'events_channels_search', 'cols': ['channel_id']},
    {'table': 'localview_events', 'cols': ['datasource_id']},
    {'table': 'event_policy_decision', 'cols': ['event_policy_decision_id']},
    {'table': 'event_policy_bill', 'cols': ['source_event_id_leg_id']},
    {'table': 'event_document_lexicon', 'cols': ['word']},
    {'table': 'jurisdiction_state_aggregate', 'cols': ['level', 'state_code', 'county', 'city']},
    {'table': 'civic_organization', 'cols': ['legacy_id']},
    {'table': 'serving_mdm_organization_nonprofit', 'cols': ['ein']},
    {'table': 'serving_mdm_bridge_org_jurisdiction', 'cols': ['org_jurisdiction_id']},
    {'table': 'jurisdiction_mapping_analysis', 'cols': ['jurisdiction_id']},
    {'table': 'jurisdiction_mapping_analysis_sources', 'cols': ['jurisdiction_id', 'website_record_key']},
    {'table': 'dq_jurisdiction_mapping_summary', 'cols': ['jurisdiction_type']},
    {'table': 'dq_jurisdiction_mapping_summary_by_acs_income_level', 'cols': ['jurisdiction_type', 'acs_income_level']},
    {'table': 'dq_jurisdiction_mapping_summary_by_acs_population_tier', 'cols': ['jurisdiction_type', 'acs_population_tier']},
    {'table': 'dq_jurisdiction_mapping_summary_municipality_places', 'cols': ['municipality_place_kind']},
    {'table': 'ballot_measures', 'cols': ['ballot_measure_uid']},  {# #783: was the one gold table with no PK #}
  ] %}

  {% for s in specs %}
    {% set rel = adapter.get_relation(database=target.database, schema='gold', identifier=s.table) %}
    {% if rel is none %}
      {{ log('ensure_gold_primary_keys: skip missing gold.' ~ s.table, info=True) }}
    {% else %}
      {% set col_list = s.cols | join(', ') %}
      {% set pk_name = s.table ~ '_pkey' %}
      {% set check_sql %}
        select 1 from pg_constraint
        where conrelid = 'gold.{{ s.table }}'::regclass and contype = 'p'
        limit 1
      {% endset %}
      {% set existing = run_query(check_sql) %}
      {% if existing is not none and existing.rows | length > 0 %}
        {{ log('ensure_gold_primary_keys: gold.' ~ s.table ~ ' already has a PK', info=True) }}
      {% else %}
        {# Prefer promoting an existing unique non-partial index on the same columns. #}
        {% set idx_sql %}
          select i.relname::text as index_name
          from pg_index ix
          join pg_class i on i.oid = ix.indexrelid
          join pg_class c on c.oid = ix.indrelid
          join pg_namespace n on n.oid = c.relnamespace
          where n.nspname = 'gold'
            and c.relname = '{{ s.table }}'
            and ix.indisunique
            and not ix.indisprimary
            and ix.indpred is null
            and (
              select array_agg(a.attname::text order by x.ordinality)
              from unnest(ix.indkey) with ordinality as x(attnum, ordinality)
              join pg_attribute a
                on a.attrelid = ix.indrelid and a.attnum = x.attnum
            ) = array[{{ "'" ~ s.cols | join("','") ~ "'" }}]::text[]
          limit 1
        {% endset %}
        {% set idx_rows = run_query(idx_sql) %}
        {% set idx_name = idx_rows.columns[0].values()[0] if (idx_rows is not none and idx_rows.rows | length > 0) else none %}

        {% if idx_name is not none %}
          {{ log('ensure_gold_primary_keys: ADD PRIMARY KEY USING INDEX ' ~ idx_name ~ ' on gold.' ~ s.table, info=True) }}
          {% if not dry_run %}
            {% do run_query('alter table gold.' ~ s.table ~ ' add constraint ' ~ pk_name ~ ' primary key using index "' ~ idx_name ~ '"') %}
            {{ log('ensure_gold_primary_keys: attached ' ~ pk_name, info=True) }}
          {% endif %}
        {% else %}
          {{ log('ensure_gold_primary_keys: ADD PRIMARY KEY (' ~ col_list ~ ') on gold.' ~ s.table, info=True) }}
          {% if not dry_run %}
            {% set null_fix %}
              select count(*) as n from gold.{{ s.table }}
              where {% for c in s.cols %}{{ c }} is null{% if not loop.last %} or {% endif %}{% endfor %}
            {% endset %}
            {% set nulls = run_query(null_fix) %}
            {% set n_null = nulls.columns[0].values()[0] if nulls is not none else -1 %}
            {% if n_null | int > 0 %}
              {{ exceptions.raise_compiler_error(
                'ensure_gold_primary_keys: gold.' ~ s.table ~ ' has ' ~ n_null
                ~ ' NULL key values; coalesce or backfill before PK (' ~ col_list ~ ')'
              ) }}
            {% endif %}
            {% do run_query('alter table gold.' ~ s.table ~ ' add constraint ' ~ pk_name ~ ' primary key (' ~ col_list ~ ')') %}
            {{ log('ensure_gold_primary_keys: attached ' ~ pk_name, info=True) }}
          {% endif %}
        {% endif %}
      {% endif %}
    {% endif %}
  {% endfor %}
{% endmacro %}
