/*
    Ordinance amendments (CORE-1.1, #237). Grain: one row per amendment of an ordinance.
    Contract enforced in _schema_ordinances.yml: PK amendment_uid, FK to ordinances,
    source_url required.

    Empty until the CORE-1.1.2 loader lands bronze.bronze_ordinance_amendments. Only
    amendments whose ordinance is in the ordinances mart are kept, so the foreign key holds.
*/

with staged as (
    select * from {{ ref('stg_ordinance_amendments') }}
    where source_url is not null
),

known_ordinance as (
    select staged.*
    from staged
    inner join {{ ref('ordinances') }} as ordinances
        on ordinances.ordinance_uid = staged.ordinance_uid
)

-- A re-load can bring the same amendment twice: keep its latest row.
select distinct on (amendment_uid)
    amendment_uid,
    ordinance_uid,
    identifier,
    description,
    amended_date,
    source_url,
    loaded_at
from known_ordinance
order by amendment_uid, loaded_at desc nulls last
