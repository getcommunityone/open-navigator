{{ config(materialized='table') }}

/*
    Mart (MDM satellite): IRS/990 nonprofit detail for organizations whose
    golden record resolved to a nonprofit (i.e. carry an EIN). One row per
    master_org_id (1:1 with the subset of mdm_organization that has an EIN).

    Splits the legacy public.organization_nonprofit serving table: identity +
    location now live on the master (mdm_organization) and the org<->address
    bridge; the financial / NTEE / GivingTuesday-990 detail lives here, keyed by
    master_org_id. Sourced from int_nonprofits_combined (NOT the retired serving
    table) joined to mdm_organization on EIN.

    NTEE major-group descriptions are inlined for serving parity with the old
    table; the canonical hierarchical taxonomy is `tag` (see tag_organization).
*/

with

nonprofits as (
    select * from {{ ref('int_nonprofits_combined') }}
),

-- Attach the golden master_org_id by EIN. mdm_organization has one row per
-- cluster with a unique non-null EIN, so this is a 1:1 join.
master as (
    select master_org_id, ein
    from {{ ref('mdm_organization') }}
    where ein is not null
),

joined as (
    select
        m.master_org_id,
        n.*
    from nonprofits as n
    join master as m on m.ein = n.ein
),

-- Guard the PK: if a single EIN ever yields >1 source row, keep the most
-- complete (prefer real 990 data, then larger revenue).
deduped as (
    select *
    from (
        select
            *,
            row_number() over (
                partition by master_org_id
                order by has_gt990_data desc nulls last, revenue desc nulls last
            ) as rn
        from joined
    ) ranked
    where rn = 1
)

select
    cast(master_org_id as text)         as master_org_id,
    cast(ein as text)                   as ein,
    cast(ntee_code as text)             as ntee_code,
    case
        when ntee_code like 'A%' then 'Arts, Culture & Humanities'
        when ntee_code like 'B%' then 'Education'
        when ntee_code like 'C%' then 'Environmental Quality, Protection'
        when ntee_code like 'D%' then 'Animal-Related'
        when ntee_code like 'E%' then 'Health'
        when ntee_code like 'F%' then 'Mental Health, Crisis Intervention'
        when ntee_code like 'G%' then 'Diseases, Disorders, Medical Disciplines'
        when ntee_code like 'H%' then 'Medical Research'
        when ntee_code like 'I%' then 'Crime, Legal Related'
        when ntee_code like 'J%' then 'Employment, Job Related'
        when ntee_code like 'K%' then 'Food, Agriculture, Nutrition'
        when ntee_code like 'L%' then 'Housing, Shelter'
        when ntee_code like 'M%' then 'Public Safety, Disaster Preparedness'
        when ntee_code like 'N%' then 'Recreation, Sports, Leisure'
        when ntee_code like 'O%' then 'Youth Development'
        when ntee_code like 'P%' then 'Human Services - Multipurpose'
        when ntee_code like 'Q%' then 'International, Foreign Affairs'
        when ntee_code like 'R%' then 'Civil Rights, Social Action, Advocacy'
        when ntee_code like 'S%' then 'Community Improvement, Capacity Building'
        when ntee_code like 'T%' then 'Philanthropy, Voluntarism'
        when ntee_code like 'U%' then 'Science and Technology Research'
        when ntee_code like 'V%' then 'Social Science Research'
        when ntee_code like 'W%' then 'Public, Society Benefit'
        when ntee_code like 'X%' then 'Religion Related'
        when ntee_code like 'Y%' then 'Mutual/Membership Benefit'
        when ntee_code like 'Z%' then 'Unknown'
        else 'Other'
    end                                 as ntee_description,
    cast(subsection as text)            as subsection_code,
    cast(classification as text)        as classification_code,
    cast(revenue as bigint)             as revenue,
    cast(assets as bigint)              as assets,
    cast(income as bigint)              as income,
    cast(tax_period as text)            as tax_period,
    cast(ruling as text)                as ruling_date,
    cast(foundation as text)            as foundation_code,
    -- GivingTuesday 990 datamart enrichment (real e-filed figures + mission)
    cast(gt990_tax_year as integer)             as gt990_tax_year,
    cast(gt990_total_revenue as bigint)         as gt990_total_revenue,
    cast(gt990_total_expenses as bigint)        as gt990_total_expenses,
    cast(gt990_total_assets as bigint)          as gt990_total_assets,
    cast(gt990_total_liabilities as bigint)     as gt990_total_liabilities,
    cast(gt990_net_assets as bigint)            as gt990_net_assets,
    cast(gt990_total_contributions as bigint)   as gt990_total_contributions,
    cast(gt990_program_service_revenue as bigint) as gt990_program_service_revenue,
    cast(gt990_source_url as text)              as gt990_source_url,
    cast(gt990_mission as text)                 as gt990_mission,
    cast(has_gt990_data as boolean)             as has_gt990_data,
    cast(datasource as text)                    as source,
    current_timestamp                           as dbt_loaded_at
from deduped
