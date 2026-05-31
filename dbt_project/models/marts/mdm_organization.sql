{{ config(materialized='table') }}

/*
    Mart (MDM Layer 5): one golden record per resolved organization, with a
    canonical org_type.

    Survivorship prefers the most-complete/most-trusted occurrence (has EIN, has
    city, has geocode; nonprofit registry > facility > AI). org_type is the most
    common NON-'other' type across the cluster (falls back to the golden record's
    type). first_seen_year / last_seen_year give the org's date span.

    parent_jurisdiction_id rolls the org up to the municipality / county that
    governs it (see int_organizations__jurisdiction_linked); picked across the
    cluster, preferring the most-trusted match (self > municipality > township >
    county). Canonical public org table — serve org search/browse from here;
    tie to person/address via the org bridges and to a jurisdiction via
    parent_jurisdiction_id.
*/

with clustered as (
    select * from {{ ref('int_organizations__jurisdiction_linked') }}
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
),

-- best parent jurisdiction per cluster: an occurrence may be unmatched while a
-- sibling occurrence matched, so pick the most-trusted non-null match.
parent as (
    select distinct on (master_org_id)
        master_org_id,
        parent_jurisdiction_id,
        jurisdiction_match_method
    from clustered
    where parent_jurisdiction_id is not null
    order by
        master_org_id,
        case jurisdiction_match_method
            when 'self'         then 1
            when 'municipality' then 2
            when 'township'     then 3
            when 'county'       then 4
            else 5
        end
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
    p.parent_jurisdiction_id,
    coalesce(p.jurisdiction_match_method, 'unmatched')  as jurisdiction_match_method,
    e.n_occurrences,
    e.n_sources,
    e.first_seen_year,
    e.last_seen_year
from golden g
join evidence e using (master_org_id)
left join type_vote v using (master_org_id)
left join parent p using (master_org_id)
