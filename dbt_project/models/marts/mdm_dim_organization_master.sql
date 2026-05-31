{{ config(materialized='table') }}

/*
    Mart (MDM Layer 5): one golden record per resolved organization, with a
    canonical org_type.

    Survivorship prefers the most-complete/most-trusted occurrence (has EIN, has
    city, has geocode; nonprofit registry > facility > AI). org_type is the most
    common NON-'other' type across the cluster (falls back to the golden record's
    type). first_seen_year / last_seen_year give the org's date span.

    Serve org search/browse from here; tie to person/address via the org bridges.
*/

with clustered as (
    select * from {{ ref('int_organizations__clustered') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by master_org_id
            order by
                (ein is not null) desc,
                (city_norm is not null) desc,
                (lat is not null) desc,
                case source_system
                    when 'bronze_organizations_nonprofits_nccs' then 1
                    when 'bronze_locations' then 2
                    when 'bronze_organizations_from_ai' then 3
                    else 4
                end,
                org_uid
        ) as rn
    from clustered
),

golden as (
    select * from ranked where rn = 1
),

-- most common non-'other' type per cluster
type_vote as (
    select distinct on (master_org_id)
        master_org_id,
        org_type as voted_type
    from clustered
    where org_type <> 'other'
    group by master_org_id, org_type
    order by master_org_id, count(*) desc
),

evidence as (
    select
        master_org_id,
        count(*)                       as n_occurrences,
        count(distinct source_system)  as n_sources,
        min(as_of_year)                as first_seen_year,
        max(as_of_year)                as last_seen_year
    from clustered
    group by 1
)

select
    g.master_org_id,
    g.org_name,
    g.org_name_norm,
    coalesce(v.voted_type, g.org_type)  as org_type,
    g.org_subtype,
    g.ein,
    g.city_norm,
    g.state_code,
    g.zip5,
    g.lat,
    g.lon,
    g.website,
    e.n_occurrences,
    e.n_sources,
    e.first_seen_year,
    e.last_seen_year
from golden g
join evidence e using (master_org_id)
left join type_vote v using (master_org_id)
