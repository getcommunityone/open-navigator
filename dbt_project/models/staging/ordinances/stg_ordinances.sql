/*
    Staging: ordinances (CORE-1.1, #237). Grain: one row per bronze row, which is one
    ordinance per jurisdiction per source platform.

    Reads bronze.bronze_ordinances when it exists. Until the CORE-1.1.2 loader creates it,
    this builds as an empty, typed relation, so dbt runs keep passing and the marts exist
    empty: an honest "no ordinances loaded yet", never stand-in rows.

    status: the source's own label (status_raw) mapped through the ordinance_status_map
    seed. A label the seed doesn't list (for example "adopted", which means final in some
    cities and awaiting signature in others) stays null rather than being guessed.

    source() and ref() are called before the guard so dbt records both dependencies at
    parse time, when the guard always takes the empty branch.
*/

{%- set bronze_ordinances = source('bronze', 'bronze_ordinances') -%}
{%- set status_map = ref('ordinance_status_map') -%}
{%- set bronze_exists = execute and adapter.get_relation(
        database=bronze_ordinances.database,
        schema=bronze_ordinances.schema,
        identifier=bronze_ordinances.identifier) is not none -%}

{% if bronze_exists %}

with source as (
    select * from {{ bronze_ordinances }}
),

status_map as (
    select raw_status_key, status from {{ status_map }}
)

select
    md5(
        source.platform_code || '|' || source.jurisdiction_id || '|' || source.platform_ordinance_id
    )                                                  as ordinance_uid,
    cast(source.jurisdiction_id as text)               as jurisdiction_id,
    cast(source.platform_code as text)                 as platform_code,
    cast(source.platform_ordinance_id as text)         as platform_ordinance_id,
    nullif(trim(cast(source.identifier as text)), '')  as identifier,
    nullif(trim(cast(source.title as text)), '')       as title,
    cast(status_map.status as text)                    as status,
    nullif(trim(cast(source.status_raw as text)), '')  as status_raw,
    nullif(cast(source.full_text as text), '')         as full_text,
    nullif(trim(cast(source.source_url as text)), '')  as source_url,
    cast(source.introduced_date as date)               as introduced_date,
    cast(source.final_action_date as date)             as final_action_date,
    cast(source.loaded_at as timestamptz)              as loaded_at
from source
left join status_map
    on status_map.raw_status_key = lower(trim(cast(source.status_raw as text)))

{% else %}

select
    cast(null as text)        as ordinance_uid,
    cast(null as text)        as jurisdiction_id,
    cast(null as text)        as platform_code,
    cast(null as text)        as platform_ordinance_id,
    cast(null as text)        as identifier,
    cast(null as text)        as title,
    cast(null as text)        as status,
    cast(null as text)        as status_raw,
    cast(null as text)        as full_text,
    cast(null as text)        as source_url,
    cast(null as date)        as introduced_date,
    cast(null as date)        as final_action_date,
    cast(null as timestamptz) as loaded_at
where false

{% endif %}
