{{ config(materialized='table') }}

/*
    Mart (MDM Layer 5): cross-reference from each source address occurrence to its
    resolved master address. One row per source occurrence.

        master_address_id  <->  (source_system, source_pk, address_uid)

    Lets any source table reach dim_address_master without being mutated, and lets
    the master roll up every contributing source row.
*/

-- distinct on address_uid: a few sources (e.g. HIFLD) repeat (source_dataset,
-- source_id), so the same occurrence key can appear twice; keep one per uid.
select distinct on (address_uid)
    master_address_id,
    source_system,
    source_pk,
    address_uid,
    raw_address
from {{ ref('int_addresses__clustered') }}
order by address_uid
