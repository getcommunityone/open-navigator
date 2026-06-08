{{
  config(
    materialized='table',
    tags=['marts', 'meetings', 'documents', 'suiteone', 'production'],
    unique_key='jurisdiction_id',
    indexes=[
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['census_geoid'], 'type': 'btree'}
    ]
  )
}}

/*
public.jurisdiction_minutes_publish_lag — per-jurisdiction statistics for how long
minutes typically take to publish after a meeting. Powers the API's "expected
minutes date" feature: expected_minutes_date = meeting_date + median_lag_days,
joined to a meeting by census_geoid.

GRAIN: one row per jurisdiction (jurisdiction_id).

SOURCE: bronze.bronze_events_meetings_municipalities_scraped (the SuiteOne
municipal-calendar crawl), restricted to MINUTES rows:
    meeting_date_source = 'suiteone_listing'
    AND doc_type        = 'minutes'
This filter is the ONLY thing scoping the model — it is NOT Tuscaloosa-specific.
Any future SuiteOne city landed with the same meeting_date_source flows through.

PUBLISH LAG (days) per minutes row:
    (raw_resource->>'minutes_published_at')::date - meeting_date
where minutes_published_at is the PDF's resolved ModDate. NULL when unresolved.

SANE-RANGE FILTER: a row only counts toward the stats when the lag is in
0..180 days inclusive. Negatives (a ModDate before the meeting) are template
noise — the PDF was authored from a stale template — and lags beyond 180 days
are absurd outliers / mis-resolved ModDates; both are excluded.

SAMPLE THRESHOLD: a jurisdiction is emitted ONLY when sample_n >= 5. A lag
estimate from fewer than 5 published minutes is not trustworthy, so we publish
nothing rather than a noisy number — downstream (the API) treats the ABSENCE of
a row as "no estimate available" and shows an explicit empty state.

Median and p90 use percentile_cont WITHIN GROUP, rounded to integer days; mean
is numeric(6,1).
*/

with minutes_lags as (

    select
        jurisdiction_id,
        census_geoid,
        rtrim(state_code)                                              as state_code,
        ( (raw_resource->>'minutes_published_at')::date - meeting_date ) as lag_days
    from {{ source('bronze', 'bronze_events_meetings_municipalities_scraped') }}
    where meeting_date_source = 'suiteone_listing'
      and doc_type            = 'minutes'
      and raw_resource->>'minutes_published_at' is not null
      and meeting_date is not null

),

in_range as (

    select
        jurisdiction_id,
        census_geoid,
        state_code,
        lag_days
    from minutes_lags
    where lag_days between 0 and 180

),

aggregated as (

    select
        jurisdiction_id,
        census_geoid,
        state_code,
        {{ state_code_to_name('state_code') }}                          as state,
        round(percentile_cont(0.5) within group (order by lag_days))::integer as median_lag_days,
        round(avg(lag_days)::numeric, 1)::numeric(6, 1)                 as mean_lag_days,
        round(percentile_cont(0.9) within group (order by lag_days))::integer as p90_lag_days,
        count(*)::integer                                               as sample_n
    from in_range
    group by jurisdiction_id, census_geoid, state_code

)

select
    jurisdiction_id,
    census_geoid,
    state_code,
    state,
    median_lag_days,
    mean_lag_days,
    p90_lag_days,
    sample_n,
    {{ dbt.current_timestamp() }}::timestamp                            as computed_at
from aggregated
-- Honest threshold: don't publish a lag estimate from fewer than 5 samples.
where sample_n >= 5
