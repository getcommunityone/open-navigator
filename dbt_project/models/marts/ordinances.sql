/*
    Ordinances (CORE-1.1, #237). Grain: one row per ordinance per jurisdiction per source
    platform. Contract enforced in _schema_ordinances.yml: PK ordinance_uid, FK to
    jurisdictions, status CHECK (the five-word vocabulary or null), source_url required.

    Empty until the CORE-1.1.2 loader lands bronze.bronze_ordinances. A row without an
    identifier or a source link isn't traceable to its document, and a row for an unknown
    jurisdiction can't satisfy the foreign key, so both are left out here; the warn-level
    tests on stg_ordinances count them in every run.
*/

with staged as (
    select * from {{ ref('stg_ordinances') }}
    where identifier is not null
      and source_url is not null
),

known_jurisdiction as (
    select staged.*
    from staged
    inner join {{ ref('jurisdictions') }} as jurisdictions
        on jurisdictions.jurisdiction_id = staged.jurisdiction_id
)

-- A re-load can bring the same ordinance twice: keep its latest row.
select distinct on (ordinance_uid)
    ordinance_uid,
    jurisdiction_id,
    platform_code,
    platform_ordinance_id,
    identifier,
    title,
    status,
    status_raw,
    full_text,
    source_url,
    introduced_date,
    final_action_date,
    loaded_at
from known_jurisdiction
order by ordinance_uid, loaded_at desc nulls last
