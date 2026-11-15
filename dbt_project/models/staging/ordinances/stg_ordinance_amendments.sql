/*
    Staging: ordinance amendments (CORE-1.1, #237). Grain: one row per bronze row, which is
    one amendment to one ordinance.

    Reads bronze.bronze_ordinance_amendments when it exists; until the CORE-1.1.2 loader
    creates it, this builds as an empty, typed relation (see stg_ordinances).

    ordinance_uid uses the same md5 as stg_ordinances, so an amendment joins to its
    ordinance on (platform_code, jurisdiction_id, platform_ordinance_id).

    source() is called before the guard so dbt records the dependency at parse time.
*/

{%- set bronze_amendments = source('bronze', 'bronze_ordinance_amendments') -%}
{%- set bronze_exists = execute and adapter.get_relation(
        database=bronze_amendments.database,
        schema=bronze_amendments.schema,
        identifier=bronze_amendments.identifier) is not none -%}

{% if bronze_exists %}

with source as (
    select * from {{ bronze_amendments }}
)

select
    md5(
        source.platform_code || '|' || source.jurisdiction_id || '|' || source.platform_ordinance_id
        || '|' || source.platform_amendment_id
    )                                                   as amendment_uid,
    md5(
        source.platform_code || '|' || source.jurisdiction_id || '|' || source.platform_ordinance_id
    )                                                   as ordinance_uid,
    nullif(trim(cast(source.identifier as text)), '')   as identifier,
    nullif(trim(cast(source.description as text)), '')  as description,
    cast(source.amended_date as date)                   as amended_date,
    nullif(trim(cast(source.source_url as text)), '')   as source_url,
    cast(source.loaded_at as timestamptz)               as loaded_at
from source

{% else %}

select
    cast(null as text)        as amendment_uid,
    cast(null as text)        as ordinance_uid,
    cast(null as text)        as identifier,
    cast(null as text)        as description,
    cast(null as date)        as amended_date,
    cast(null as text)        as source_url,
    cast(null as timestamptz) as loaded_at
where false

{% endif %}
