{#
  One-time repair for #501: replace id-shaped jurisdiction_name values that were
  already written into tables a normal `dbt run` cannot rewrite.

  Why a run-operation: `civic_event` is written by the Python promote step
  (ingestion.youtube.promote_to_c1_event), and the AI-extraction event marts
  (event_meeting + its event_* children) are `incremental, append,
  full_refresh=false`, so they keep the name they copied from civic_event at build
  time. Staging/view fixes heal everything rebuilt from bronze; these rows need a
  targeted UPDATE.

  Order:
    1. civic_event: name from int_jurisdictions by jurisdiction_id
       (NULL when the id is unknown: an id is never kept as a name).
    2. each append-only event mart: name from the repaired civic_event, joined on
       c1_event_id = civic_event.id (NULL when there is no civic_event row).
  Only rows whose stored name is id-shaped (or equals the id) are touched.
  Afterwards rebuild the table marts that read these (see the #501 PR).

  Usage:
    dbt run-operation repair_id_shaped_jurisdiction_names                     # dry run: counts only
    dbt run-operation repair_id_shaped_jurisdiction_names --args '{dry_run: false}'
#}
{% macro repair_id_shaped_jurisdiction_names(dry_run=true) %}
    {%- set civic_event = source('civic_core', 'civic_event') -%}
    {%- set juris = ref('int_jurisdictions') -%}
    {%- set event_marts = [
        'event_meeting', 'event_decision', 'event_bill', 'event_person',
        'event_place', 'event_financial_item', 'event_topic',
    ] -%}

    {%- set ce_bad -%}
        ({{ jurisdiction_name_is_id_shaped('ce.jurisdiction_name') }}
         or ce.jurisdiction_name = ce.jurisdiction_id)
    {%- endset -%}

    {%- set count_ce = run_query('select count(*) from ' ~ civic_event ~ ' ce where ' ~ ce_bad).columns[0].values()[0] -%}
    {{ log('civic_event: ' ~ count_ce ~ ' id-shaped jurisdiction_name rows', info=true) }}

    {%- if not dry_run -%}
        {%- set upd_ce -%}
            update {{ civic_event }} ce
            set jurisdiction_name = (
                select j.name from {{ juris }} j where j.jurisdiction_id = ce.jurisdiction_id
            )
            where {{ ce_bad }}
        {%- endset -%}
        {%- do run_query(upd_ce) -%}
        {{ log('civic_event: repaired', info=true) }}
    {%- endif -%}

    {%- for m in event_marts -%}
        {%- set rel = ref(m) -%}
        {%- set bad = jurisdiction_name_is_id_shaped('t.jurisdiction_name') -%}
        {%- set n = run_query('select count(*) from ' ~ rel ~ ' t where ' ~ bad).columns[0].values()[0] -%}
        {{ log(m ~ ': ' ~ n ~ ' id-shaped jurisdiction_name rows', info=true) }}
        {%- if not dry_run and n | int > 0 -%}
            {%- set upd -%}
                update {{ rel }} t
                set jurisdiction_name = (
                    select ce.jurisdiction_name
                    from {{ civic_event }} ce
                    where ce.id = t.c1_event_id
                      and not {{ jurisdiction_name_is_id_shaped('ce.jurisdiction_name') }}
                )
                where {{ bad }}
            {%- endset -%}
            {%- do run_query(upd) -%}
            {{ log(m ~ ': repaired', info=true) }}
        {%- endif -%}
    {%- endfor -%}

    {%- if not dry_run -%}
        {%- do run_query('commit') -%}
    {%- endif -%}
{% endmacro %}
