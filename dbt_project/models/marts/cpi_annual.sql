{{ config(materialized='table', on_schema_change='fail') }}

/*
Annual-average BLS CPI index — the public serving wrapper over
`stg_bls__cpi_annual`, one row per (series_id, year).

WHY THIS EXISTS: the frontend real-dollar / inflation toggle reads CPI via
`/api/cpi/annual`. The staging view lives only in the `staging` schema, which is
dev/gold-side and is NEVER mirrored to the Neon serving DB — so prod (Neon) had
no relation to read and the endpoint 500'd. Promoting CPI to a mart lands it in
`gold`, `publish_public_serving` exposes it back into `public`, and the Neon
civic allow-list (`sync_public_to_neon.CIVIC_SERVING`) mirrors it. Tiny
(~15 rows/series), so a full table — not incremental.

`year` is stored as an INTEGER per the calendar-year storage rule (bronze keeps
the source-native VARCHAR(4); we cast here). The API serializes it to a string
at the JSON boundary.
*/

with annual as (
    select * from {{ ref('stg_bls__cpi_annual') }}
)

select
    series_id,
    year::int             as year,
    index_value,
    from_official_annual
from annual
