/*
Partition management for the public `event_*` AI-extraction marts.

dbt-postgres has no `partition_by` config and its `incremental` materialization
resolves the target relation from the cache BEFORE pre-hooks run, so a
hook-created partitioned parent collides with dbt's `create table as` on the
first build. The working pattern is therefore:

  1. `dbt run-operation bootstrap_event_person`  (once, creates the partitioned
     parent + indexes + initial monthly partitions — idempotent)
  2. `dbt build --select event_person`           (incremental APPEND only;
     Postgres routes rows to the right monthly partition)
  3. `on-run-start: ensure_event_partitions(...)` rolls the next month's
     partition forward on every run (guarded — no-op until the parent exists).

Keep the parent DDL in `bootstrap_*` in sync with the model SELECT columns.
*/

{% macro ensure_event_partitions(relation_name, start_year=2026, start_month=1) %}
{%- if execute -%}
  {%- set check = run_query("select to_regclass('" ~ relation_name ~ "') as r") -%}
  {%- if check and check.rows and check.rows[0][0] is not none -%}
    {%- set parts = relation_name.split('.') -%}
    {%- set schema = parts[0] if parts | length > 1 else target.schema -%}
    {%- set tbl = parts[-1] -%}
    {%- set today = modules.datetime.date.today() -%}
    {#- create through the NEXT calendar month so live inserts never miss a range -#}
    {%- set last_index = (today.year - start_year) * 12 + (today.month - start_month) + 1 -%}
    {%- for i in range(0, last_index + 1) -%}
      {%- set y = start_year + ((start_month - 1 + i) // 12) -%}
      {%- set m = ((start_month - 1 + i) % 12) + 1 -%}
      {%- set ny = y + (1 if m == 12 else 0) -%}
      {%- set nm = (m % 12) + 1 -%}
create table if not exists {{ schema }}.{{ '%s_p%04d%02d' | format(tbl, y, m) }}
    partition of {{ relation_name }}
    for values from ('{{ '%04d-%02d-01' | format(y, m) }}') to ('{{ '%04d-%02d-01' | format(ny, nm) }}');
    {% endfor -%}
create table if not exists {{ schema }}.{{ tbl }}_pdefault partition of {{ relation_name }} default;
  {%- else -%}
select 1;
  {%- endif -%}
{%- else -%}
select 1;
{%- endif -%}
{% endmacro %}


{% macro bootstrap_event_person() %}
  {% set ddl %}
    create table if not exists public.event_person (
        id                            text        not null,
        extraction_key                text        not null,
        analysis_id                   integer,
        legacy_event_id               integer,
        c1_event_id                   varchar(50),
        state_code                    varchar(2),
        state                         text,
        jurisdiction_name             varchar(200),
        jurisdiction_type             varchar(50),
        city                          varchar(100),
        person_id                     text,
        full_name                     text,
        role                          text,
        org_id                        text,
        party_affiliation             text,
        is_lobbyist                   boolean,
        lobbyist_registration_number  text,
        lobbyist_clients              jsonb,
        wikidata_qid                  text,
        appeared_as                   text,
        source_ai_model               varchar(100),
        extracted_at                  timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);

    create index if not exists ix_event_person_c1_event  on public.event_person (c1_event_id);
    create index if not exists ix_event_person_state      on public.event_person (state_code);
    create index if not exists ix_event_person_extracted  on public.event_person (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_person')) %}
  {{ log("bootstrapped partitioned table public.event_person (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_decision() %}
  {% set ddl %}
    create table if not exists public.event_decision (
        id                       text        not null,
        extraction_key           text        not null,
        analysis_id              integer,
        legacy_event_id          integer,
        c1_event_id              varchar(50),
        state_code               varchar(2),
        state                    text,
        jurisdiction_name        varchar(200),
        jurisdiction_type        varchar(50),
        city                     varchar(100),
        decision_id              text,
        subject_id               text,
        primary_place_id         text,
        place_refs               jsonb,
        legislation_refs         jsonb,
        financial_item_refs      jsonb,
        headline                 text,
        decision_statement       text,
        primary_theme            text,
        outcome                  text,
        vote_tally               jsonb,
        human_element            jsonb,
        competing_views          jsonb,
        smart_brevity            jsonb,
        diagram_timeline         text,
        diagram_timeline_lines   jsonb,
        diagram_mindmap          text,
        diagram_mindmap_lines    jsonb,
        source_ai_model          varchar(100),
        extracted_at             timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);

    create index if not exists ix_event_decision_c1_event  on public.event_decision (c1_event_id);
    create index if not exists ix_event_decision_state      on public.event_decision (state_code);
    create index if not exists ix_event_decision_extracted  on public.event_decision (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_decision')) %}
  {{ log("bootstrapped partitioned table public.event_decision (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_place() %}
  {% set ddl %}
    create table if not exists public.event_place (
        id                   text        not null,
        extraction_key       text        not null,
        analysis_id          integer,
        legacy_event_id      integer,
        c1_event_id          varchar(50),
        state_code           varchar(2),
        state                text,
        jurisdiction_name    varchar(200),
        jurisdiction_type    varchar(50),
        city                 varchar(100),
        place_id             text,
        raw_text             text,
        normalized_address   text,
        place_type           text,
        street_address       text,
        place_city           text,
        place_state_code     text,
        geocode_query        text,
        latitude             double precision,
        longitude            double precision,
        geocode_status       text,
        linked_decision_ids  jsonb,
        linked_item_ids      jsonb,
        mention_count        integer,
        source_ai_model      varchar(100),
        extracted_at         timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);
    create index if not exists ix_event_place_c1_event  on public.event_place (c1_event_id);
    create index if not exists ix_event_place_state      on public.event_place (state_code);
    create index if not exists ix_event_place_extracted  on public.event_place (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_place')) %}
  {{ log("bootstrapped partitioned table public.event_place (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_financial_item() %}
  {% set ddl %}
    create table if not exists public.event_financial_item (
        id                       text        not null,
        extraction_key           text        not null,
        analysis_id              integer,
        legacy_event_id          integer,
        c1_event_id              varchar(50),
        state_code               varchar(2),
        state                    text,
        jurisdiction_name        varchar(200),
        jurisdiction_type        varchar(50),
        city                     varchar(100),
        financial_item_id        text,
        decision_id              text,
        subject_id               text,
        event_description        text,
        item_description         text,
        amount                   numeric,
        amount_type              text,
        amount_qualifier         text,
        currency                 text,
        item_date                date,
        item_date_type           text,
        org_id                   text,
        org_role                 text,
        authorized_by_person_id  text,
        funding_source           text,
        notes                    text,
        source_ai_model          varchar(100),
        extracted_at             timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);
    create index if not exists ix_event_financial_item_c1_event  on public.event_financial_item (c1_event_id);
    create index if not exists ix_event_financial_item_state      on public.event_financial_item (state_code);
    create index if not exists ix_event_financial_item_extracted  on public.event_financial_item (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_financial_item')) %}
  {{ log("bootstrapped partitioned table public.event_financial_item (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_topic() %}
  {% set ddl %}
    create table if not exists public.event_topic (
        id                            text        not null,
        extraction_key                text        not null,
        analysis_id                   integer,
        legacy_event_id               integer,
        c1_event_id                   varchar(50),
        state_code                    varchar(2),
        state                         text,
        jurisdiction_name             varchar(200),
        jurisdiction_type             varchar(50),
        city                          varchar(100),
        decision_id                   text,
        primary_theme                 text,
        primary_theme_cofog           text,
        secondary_theme               text,
        secondary_theme_cofog         text,
        ntee_code                     text,
        ntee_major_group              text,
        ntee_category_label           text,
        secondary_ntee_code           text,
        secondary_ntee_major_group    text,
        secondary_ntee_category_label text,
        primary_org_ids               jsonb,
        topic                         text,
        headline                      text,
        source_ai_model               varchar(100),
        extracted_at                  timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);
    create index if not exists ix_event_topic_c1_event  on public.event_topic (c1_event_id);
    create index if not exists ix_event_topic_state      on public.event_topic (state_code);
    create index if not exists ix_event_topic_extracted  on public.event_topic (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_topic')) %}
  {{ log("bootstrapped partitioned table public.event_topic (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_bill() %}
  {% set ddl %}
    create table if not exists public.event_bill (
        id                   text        not null,
        extraction_key       text        not null,
        analysis_id          integer,
        legacy_event_id      integer,
        c1_event_id          varchar(50),
        state_code           varchar(2),
        state                text,
        jurisdiction_name    varchar(200),
        jurisdiction_type    varchar(50),
        city                 varchar(100),
        leg_id               text,
        leg_type             text,
        official_number      text,
        title                text,
        jurisdiction         text,
        year                 text,
        status               text,
        relevance            text,
        url                  text,
        source_ai_model      varchar(100),
        extracted_at         timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);
    create index if not exists ix_event_bill_c1_event  on public.event_bill (c1_event_id);
    create index if not exists ix_event_bill_state      on public.event_bill (state_code);
    create index if not exists ix_event_bill_extracted  on public.event_bill (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_bill')) %}
  {{ log("bootstrapped partitioned table public.event_bill (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_organization() %}
  {# AGGREGATED grain: one row per org (normalized name + state) across events,
     so it carries first/last-seen event resolution rather than a single c1_event_id. #}
  {% set ddl %}
    create table if not exists public.event_organization (
        id                    text        not null,
        extraction_key        text        not null,
        org_id                text,
        org_name              text,
        org_name_normalized   text,
        state_code            text,
        state                 text,
        org_type              text,
        org_subtype           text,
        is_lobbyist_entity    boolean,
        lobbying_clients      jsonb,
        party_affiliation     text,
        ein                   text,
        wikidata_qid          text,
        ntee_major_group      text,
        ntee_category_label   text,
        ntee_code             text,
        role_in_meeting       text,
        financial_interest    text,
        first_seen_analysis_id integer,
        last_seen_analysis_id  integer,
        first_c1_event_id     varchar(50),
        last_c1_event_id      varchar(50),
        source_ai_model       varchar(100),
        extracted_at          timestamp   not null,
        primary key (extraction_key, extracted_at)
    ) partition by range (extracted_at);
    create index if not exists ix_event_organization_state        on public.event_organization (state_code);
    create index if not exists ix_event_organization_last_event   on public.event_organization (last_c1_event_id);
    create index if not exists ix_event_organization_extracted    on public.event_organization (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_organization')) %}
  {{ log("bootstrapped partitioned table public.event_organization (+ monthly partitions)", info=True) }}
{% endmacro %}
