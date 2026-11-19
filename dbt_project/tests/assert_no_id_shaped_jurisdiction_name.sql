{{ config(severity='error', tags=['jurisdiction_name', 'serving']) }}

/*
#501: jurisdiction_name is the human display name, never an id.

Fails (returns rows) when a served table carries an id-shaped jurisdiction_name:
  - the slug id         `{place_slug}_{geoid}`  e.g. chilton_01021
  - the legacy county   `c-{USPS}-{geoid}`      e.g. c-AL-01021

Checked relations:
  - the four models #501 names (via ref, so the test runs after they build):
    event_meeting, event_decision, question_instance, item_interestingness;
  - every other relation in the `public` schema that has a jurisdiction_name
    column, discovered at run time, so a new serving view is covered without
    editing this test.

Output: one row per (relation, offending name) with its row count.
*/

{%- set checked = [
    ref('event_meeting'),
    ref('event_decision'),
    ref('question_instance'),
    ref('item_interestingness'),
] -%}

{%- set relations = [] -%}
{%- for r in checked -%}
    {%- do relations.append(r ~ '') -%}
{%- endfor -%}

{%- if execute -%}
    {%- set public_sql -%}
        select quote_ident(c.table_schema) || '.' || quote_ident(c.table_name)
        from information_schema.columns c
        where c.table_schema = 'public'
          and c.column_name = 'jurisdiction_name'
        order by 1
    {%- endset -%}
    {%- for row in run_query(public_sql).rows -%}
        {%- if row[0] not in relations -%}
            {%- do relations.append(row[0]) -%}
        {%- endif -%}
    {%- endfor -%}
{%- endif -%}

{% for rel in relations %}
select
    '{{ rel }}'::text            as relation,
    jurisdiction_name::text      as jurisdiction_name,
    count(*)                     as row_count
from {{ rel }}
where {{ jurisdiction_name_is_id_shaped('jurisdiction_name::text') }}
group by 2
{% if not loop.last %}union all{% endif %}
{% endfor %}
