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
        event_person_id               text        not null,
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
        display_name                  text,
        role                          text,
        is_lobbyist                   boolean,
        appeared_as                   text,
        source_ai_model               varchar(100),
        extracted_at                  timestamp   not null,
        primary key (event_person_id, extracted_at),
        unique (extraction_key, extracted_at)
    ) partition by range (extracted_at);

    -- migrate pre-existing installs created before display_name was added
    alter table public.event_person add column if not exists display_name text;

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
        event_decision_id        text        not null,
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
        primary key (event_decision_id, extracted_at),
        unique (extraction_key, extracted_at)
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
        event_place_id       text        not null,
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
        primary key (event_place_id, extracted_at),
        unique (extraction_key, extracted_at)
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
        event_financial_item_id  text        not null,
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
        event_description        text,
        amount                   numeric,
        amount_type              text,
        currency                 text,
        funding_source           text,
        source_ai_model          varchar(100),
        extracted_at             timestamp   not null,
        primary key (event_financial_item_id, extracted_at),
        unique (extraction_key, extracted_at)
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
        event_topic_id                text        not null,
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
        headline                      text,
        source_ai_model               varchar(100),
        extracted_at                  timestamp   not null,
        primary key (event_topic_id, extracted_at),
        unique (extraction_key, extracted_at)
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
        event_bill_id        text        not null,
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
        status               text,
        relevance            text,
        source_ai_model      varchar(100),
        extracted_at         timestamp   not null,
        primary key (event_bill_id, extracted_at),
        unique (extraction_key, extracted_at)
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

    -- Event-meeting links. The aggregated org grain resolves a first- and
    -- last-seen analysis, both of which are real event_meeting rows. Types match
    -- (integer -> event_meeting.event_meeting_id integer). Guarded so re-running
    -- bootstrap against an already-populated table back-fills the FKs.
    do $$ begin
      if not exists (
          select 1 from pg_constraint
          where conname = 'event_organization_first_meeting_fk'
            and conrelid = 'public.event_organization'::regclass
      ) then
        alter table public.event_organization
          add constraint event_organization_first_meeting_fk
          foreign key (first_seen_analysis_id) references public.event_meeting(event_meeting_id);
      end if;
      if not exists (
          select 1 from pg_constraint
          where conname = 'event_organization_last_meeting_fk'
            and conrelid = 'public.event_organization'::regclass
      ) then
        alter table public.event_organization
          add constraint event_organization_last_meeting_fk
          foreign key (last_seen_analysis_id) references public.event_meeting(event_meeting_id);
      end if;
    end $$;

    create index if not exists ix_event_organization_state        on public.event_organization (state_code);
    create index if not exists ix_event_organization_first_event  on public.event_organization (first_c1_event_id);
    create index if not exists ix_event_organization_last_event   on public.event_organization (last_c1_event_id);
    create index if not exists ix_event_organization_first_anls   on public.event_organization (first_seen_analysis_id);
    create index if not exists ix_event_organization_last_anls    on public.event_organization (last_seen_analysis_id);
    create index if not exists ix_event_organization_extracted    on public.event_organization (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {% do run_query(ensure_event_partitions('public.event_organization')) %}
  {{ log("bootstrapped partitioned table public.event_organization (+ monthly partitions)", info=True) }}
{% endmacro %}


{% macro bootstrap_event_meeting() %}
  {# Meeting-level PARENT of the AI-extraction family. NON-partitioned on purpose:
     a single-column PK (event_meeting_id) is required so the partitioned child
     tables can declare a FOREIGN KEY into it (a partitioned table cannot be a
     single-column FK target). One row per analysis; event_meeting_id == the
     bronze analysis id, which is exactly the children's analysis_id. #}
  {% set ddl %}
    create table if not exists public.event_meeting (
        event_meeting_id     integer     not null,
        legacy_event_id      integer,
        c1_event_id          varchar(50),
        state_code           varchar(2),
        state                text,
        jurisdiction_name    varchar(200),
        jurisdiction_type    varchar(50),
        city                 varchar(100),
        meeting_id           text,
        body_name            text,
        meeting_date         text,
        event_date           text,
        jurisdiction         text,
        meeting_summary      text,
        agenda_summary       text,
        session_info         jsonb,
        video_id             varchar(50),
        source_ai_model      varchar(100),
        extracted_at         timestamp   not null,
        primary key (event_meeting_id)
    );

    -- Canonical event link. c1_event.legacy_id is the real PK; c1_event.id only
    -- carries a unique INDEX (not a constraint) so it can't be an FK target.
    do $$ begin
      if not exists (
          select 1 from pg_constraint
          where conname = 'event_meeting_c1_event_fk'
            and conrelid = 'public.event_meeting'::regclass
      ) then
        alter table public.event_meeting
          add constraint event_meeting_c1_event_fk
          foreign key (legacy_event_id) references public.c1_event(legacy_id);
      end if;
    end $$;

    create index if not exists ix_event_meeting_c1_event  on public.event_meeting (c1_event_id);
    create index if not exists ix_event_meeting_legacy    on public.event_meeting (legacy_event_id);
    create index if not exists ix_event_meeting_state     on public.event_meeting (state_code);
    create index if not exists ix_event_meeting_extracted on public.event_meeting (extracted_at);
  {% endset %}
  {% do run_query(ddl) %}
  {{ log("bootstrapped table public.event_meeting", info=True) }}
{% endmacro %}


{% macro migrate_event_extraction_keys() %}
  {# One-shot, idempotent migration for ALREADY-POPULATED child tables. Renames
     the surrogate key id -> event_<entity>_id, moves the PK onto it, preserves
     the extraction_key dedup guarantee as a UNIQUE, and adds the FK into the
     event_meeting parent. `bootstrap_event_meeting` + a build of event_meeting
     MUST run first (the FK target must exist and be populated). Safe to re-run. #}
  {% set tables = [
      ('event_person',         'event_person_id'),
      ('event_decision',       'event_decision_id'),
      ('event_place',          'event_place_id'),
      ('event_financial_item', 'event_financial_item_id'),
      ('event_topic',          'event_topic_id'),
      ('event_bill',           'event_bill_id')
  ] %}
  {% for tbl, idcol in tables %}
  {% set sql %}
  do $$
  declare
    old_pk text;
  begin
    -- 1. rename surrogate key column: id -> {{ idcol }}
    if exists (select 1 from information_schema.columns
               where table_schema='public' and table_name='{{ tbl }}' and column_name='id')
       and not exists (select 1 from information_schema.columns
               where table_schema='public' and table_name='{{ tbl }}' and column_name='{{ idcol }}') then
      execute 'alter table public.{{ tbl }} rename column id to {{ idcol }}';
    end if;

    -- 2. move PK onto ({{ idcol }}, extracted_at) if it isn't already there
    if not exists (
        select 1
        from pg_index i
        join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
        where i.indrelid = 'public.{{ tbl }}'::regclass and i.indisprimary and a.attname = '{{ idcol }}'
    ) then
      select conname into old_pk from pg_constraint
        where conrelid = 'public.{{ tbl }}'::regclass and contype = 'p' limit 1;
      if old_pk is not null then
        execute 'alter table public.{{ tbl }} drop constraint ' || quote_ident(old_pk);
      end if;
      execute 'alter table public.{{ tbl }} add constraint {{ tbl }}_pkey primary key ({{ idcol }}, extracted_at)';
    end if;

    -- 3. preserve the extraction_key dedup guarantee as a UNIQUE
    if not exists (select 1 from pg_constraint
                   where conname = '{{ tbl }}_extraction_key_uniq'
                     and conrelid = 'public.{{ tbl }}'::regclass) then
      execute 'alter table public.{{ tbl }} add constraint {{ tbl }}_extraction_key_uniq unique (extraction_key, extracted_at)';
    end if;

    -- 4. FK into the event_meeting parent
    if not exists (select 1 from pg_constraint
                   where conname = '{{ tbl }}_event_meeting_fk'
                     and conrelid = 'public.{{ tbl }}'::regclass) then
      execute 'alter table public.{{ tbl }} add constraint {{ tbl }}_event_meeting_fk '
              'foreign key (analysis_id) references public.event_meeting(event_meeting_id)';
    end if;
  end $$;
  {% endset %}
  {% do run_query(sql) %}
  {{ log("migrated keys + constraints on public." ~ tbl, info=True) }}
  {% endfor %}
{% endmacro %}
