{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'}
    ],
    post_hook=[
      "CREATE INDEX IF NOT EXISTS bills_title_fts_idx ON {{ this }} USING gin (to_tsvector('english', coalesce(title, '')))"
    ]
  )
}}

/*
    Mart: public.bills — one row per OpenStates bill (PK bill_uid). Built from
    int_bills__jurisdiction_linked. Serves the bills browse/search and the geography
    map (via rpt_bill_map_aggregate).

    jurisdiction_id is a NULLABLE FK -> jurisdictions.jurisdiction_id (state-level
    row): federal / unmapped bills are allowed. subject and classification are kept
    as jsonb (the topic source exploded in rpt_bill_map_aggregate). year is an
    INTEGER (string only at the JSON/wire boundary, not here).

    Contract enforced: PK + FK declared so Postgres enforces them.
*/

with

linked as (
    select * from {{ ref('int_bills__jurisdiction_linked') }}
)

select
    md5('openstates_bill|' || ocd_bill_id)                 as bill_uid,
    ocd_bill_id,
    identifier,
    title,
    classification,
    subject,
    session_identifier,
    session_name,
    ocd_jurisdiction_id,
    state_code,
    jurisdiction_id,
    latest_action_date,
    latest_action_description,
    year,
    current_timestamp                                      as dbt_loaded_at
from linked
