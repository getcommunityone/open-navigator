{{ config(materialized='table') }}

/*
    Intermediate (MDM): deterministic address clustering.

    Addresses are structured, so they resolve deterministically on the exact
    normalized-address key — no probabilistic chaining (which over-merged whole
    ZIPs under Splink). master_address_id = address_match_key when present;
    streetless rows (null key, by design — see address_match_key macro) stay
    singletons keyed by their own address_uid so they never collapse together.

    Grain: one row per source address occurrence, now carrying its cluster id.
    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 3, address pipeline).
*/

select
    *,
    coalesce(address_match_key, address_uid) as master_address_id
from {{ ref('int_addresses__unioned') }}
