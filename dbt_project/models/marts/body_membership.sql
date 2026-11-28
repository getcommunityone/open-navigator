{{ config(
    materialized='table',
    on_schema_change='fail',
    contract={'enforced': true},
    tags=['marts', 'bodies', 'api'],
    indexes=[
      {'columns': ['body_membership_id'], 'unique': True},
      {'columns': ['governing_body_id'], 'type': 'btree'},
      {'columns': ['person_id'], 'type': 'btree'}
    ]
) }}

/*
    body_membership (#1443): who sits on each governing body, in what role. Grain: one row per body x member x role
    (a council member who is also president pro tem has two rows). PK body_membership_id =
    md5(governing_body_id | member_key | role), member_key = person_id, else legislator_person_uid, else
    '<source>:<name key>'.

    From int_body_member__candidate (officials data and its terms, the council roster scraper, Legistar office
    records, OpenStates chambers). When two sources give the same member the same role on the same body, the first in
    that order wins. No row comes from speech: a person heard in a meeting is never made a member here.

    FKs: governing_body_id -> governing_body, person_id -> person_government (nullable: a Legistar member we have no
    official row for), legislator_person_uid -> legislator (state chambers).
*/

with candidate as (
    select
        c.*,
        md5(c.jurisdiction_id || '|' || c.body_key)                          as governing_body_id,
        coalesce(c.person_id, c.legislator_person_uid,
                 c.source || ':' || coalesce({{ person_name_key('c.member_name') }}, lower(c.member_name))) as member_key,
        case c.source when 'officials' then 1 when 'council_roster' then 2 when 'legistar' then 3 else 4 end as source_rank
    from {{ ref('int_body_member__candidate') }} as c
),

ranked as (
    select distinct on (c.governing_body_id, c.member_key, c.role)
        c.*
    from candidate as c
    join {{ ref('governing_body') }} as g on g.governing_body_id = c.governing_body_id
    order by c.governing_body_id, c.member_key, c.role, c.source_rank, c.is_current desc, c.start_date desc nulls last
)

select
    md5(r.governing_body_id || '|' || r.member_key || '|' || r.role)::text  as body_membership_id,
    r.governing_body_id::text                                               as governing_body_id,
    r.jurisdiction_id::text                                                 as jurisdiction_id,
    p.person_id::text                                                       as person_id,
    l.person_uid::text                                                      as legislator_person_uid,
    r.member_name::text                                                     as member_name,
    r.role::text                                                            as role,
    r.role_title::text                                                      as role_title,
    r.district::text                                                        as district,
    r.start_date::date                                                      as start_date,
    r.end_date::date                                                        as end_date,
    r.is_current::boolean                                                   as is_current,
    r.source::text                                                          as source,
    r.source_url::text                                                      as source_url,
    r.confidence::numeric(3, 2)                                             as confidence
from ranked as r
left join {{ ref('person_government') }} as p on p.person_id = r.person_id
left join {{ ref('legislator') }} as l on l.person_uid = r.legislator_person_uid
