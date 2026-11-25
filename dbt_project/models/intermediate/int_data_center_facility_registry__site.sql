{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Which data_center_site each US Data Center Registry data center belongs to (#958).
    Grain: one row per registry record with facility_type = 'data_center' and a state.
    (Crypto mines, facility_type 'crypto_mining', are not data centers and are left out.)

    A registry record joins an existing Epoch AI site only when, in the same state, their names
    are EQUAL once normalised (lower case, punctuation dropped, and the words "data center(s)",
    "campus", "dc", "ai", "the" removed: "Google Cedar Rapids Data Center Campus" = "Google Cedar
    Rapids"), and that pairing is one-to-one: the Epoch site has exactly one such registry
    record and the record exactly one such site. Anything else (no equal name, or several) is
    its own site. A close-but-unequal name never merges: in one city a 0.6 word similarity
    paired "Google New Albany" with fifteen different facilities (#958 trial).

    data_center_site_id: the Epoch site's id (md5('epoch|' || name)) when matched (match_basis
    'epoch_same_name'), else md5('us_data_center_registry|' || registry id) ('own_site').
*/

{%- set norm = "btrim(regexp_replace(regexp_replace(lower({}), '\\m(data cent(er|re)s?|campus|dc|ai|the)\\M', ' ', 'g'), '[^a-z0-9]+', ' ', 'g'))" %}

with registry as (
    select *, {{ norm.format('facility_name') }} as name_key
    from {{ ref('stg_data_center_facility_registry') }}
    where facility_type = 'data_center' and state_code is not null and facility_name is not null
),

epoch as (
    select
        md5('epoch|' || name)       as data_center_site_id,
        state_code,
        {{ norm.format('name') }}   as name_key
    from {{ ref('stg_epoch_data_center') }}
    where state_code is not null
),

pairs as (
    select r.registry_id, e.data_center_site_id
    from registry as r
    inner join epoch as e on e.state_code = r.state_code and e.name_key = r.name_key and r.name_key <> ''
),

one_to_one as (
    select p.*
    from pairs as p
    where (select count(*) from pairs as x where x.registry_id = p.registry_id) = 1
      and (select count(*) from pairs as y where y.data_center_site_id = p.data_center_site_id) = 1
)

select
    r.registry_id::text                                                                     as registry_id,
    coalesce(m.data_center_site_id, md5('us_data_center_registry|' || r.registry_id))::text as data_center_site_id,
    (case when m.data_center_site_id is not null then 'epoch_same_name' else 'own_site' end)::text as match_basis
from registry as r
left join one_to_one as m on m.registry_id = r.registry_id
