{{ config(materialized='table') }}

/*
    Intermediate (#1274): one row per (state_code, session_identifier) of OpenStates state bills, with the
    first year a bill was introduced, the last year with an action, whether it looks like a special session,
    and is_closed: the session is over in our data. Used to call a bill that was never enacted "failed" once
    its session ended.

    is_closed: the same state has another session that ends in a later year, or a later REGULAR session that
    opened in or after this session's last year (e.g. NJ 222 opened in January 2026 as 221 closed). Years after
    the current year are ignored (a few source rows carry typos such as 8019). Special sessions (identifiers like
    2021s1, 2018S2, "special") never close the regular session they run beside.
*/

with

spans as (
    select
        state_code,
        session_identifier,
        min(extract(year from first_action_date)::int)
            filter (where extract(year from first_action_date) <= extract(year from current_date)) as start_year,
        max(year) filter (where year <= extract(year from current_date)::int)                     as last_year,
        bool_or(coalesce(session_identifier, '') ~* '(special|[0-9]s[0-9]+$|^[0-9]{4}s|ss[0-9]*$|x[0-9]*$)') as is_special
    from {{ ref('stg_openstates__bill') }}
    where state_code is not null
    group by state_code, session_identifier
)

select
    s.state_code::text          as state_code,
    s.session_identifier::text  as session_identifier,
    s.start_year::integer       as start_year,
    s.last_year::integer        as last_year,
    s.is_special                as is_special,
    exists (
        select 1 from spans o
        where o.state_code = s.state_code
          and o.session_identifier is distinct from s.session_identifier
          and (
                o.last_year > s.last_year
             or (not o.is_special and o.start_year > s.start_year and o.start_year >= s.last_year)
          )
    )                           as is_closed
from spans s
