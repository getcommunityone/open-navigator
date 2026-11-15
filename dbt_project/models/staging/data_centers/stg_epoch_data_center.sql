/*
    Staging: Epoch AI data center sites (DC-4.1, #249). Source: Epoch AI, "AI data
    centers", CC BY 4.0 (credit Epoch AI).
    Grain: one row per site name, from the newest snapshot that lists it.

    is_listed is true when the site is in the newest snapshot loaded. A site that drops
    out keeps its last row here (is_listed = false, last_seen_on = its last snapshot), so
    it stays visible downstream instead of vanishing.

    Owner / Users / Project carry Epoch's confidence tags (#confident, #likely,
    #speculative): #confident is dropped, the other two become "(likely)" and
    "(speculative)" so the page never states a guess as fact.
*/

with rows as (
    select
        name,
        snapshot_on,
        source_url,
        record,
        loaded_at
    from {{ source('bronze', 'bronze_epoch_data_centers') }}
    where nullif(btrim(name), '') is not null
),

newest_snapshot as (
    select max(snapshot_on) as snapshot_on from rows
),

seen as (
    select
        name,
        min(snapshot_on) as first_seen_on,
        max(snapshot_on) as last_seen_on
    from rows
    group by name
),

latest as (
    select distinct on (name) *
    from rows
    order by name, snapshot_on desc, loaded_at desc
),

typed as (
    select
        l.name,
        l.source_url,
        l.snapshot_on,
        {{ epoch_confidence_text("l.record ->> 'Owner'") }}      as owner,
        {{ epoch_confidence_text("l.record ->> 'Users'") }}      as users,
        {{ epoch_confidence_text("l.record ->> 'Project'") }}    as project,
        nullif(btrim(l.record ->> 'Address'), '')                as address,
        nullif(btrim(l.record ->> 'Country'), '')                as country,
        nullif(btrim(l.record ->> 'Selected sources'), '')       as selected_sources
    from latest as l
)

select
    t.name,
    t.owner,
    t.users,
    t.project,
    t.address,
    t.country,
    -- A US address ending in ", XX" or ", XX 12345" gives the state; anything else is null.
    case
        when t.country in ('United States', 'United States of America', 'USA', 'US')
            then {{ us_state_code_from_address('t.address') }}
    end                                                      as state_code,
    t.selected_sources,
    t.source_url,
    s.first_seen_on,
    s.last_seen_on,
    (s.last_seen_on = n.snapshot_on)                         as is_listed
from typed as t
inner join seen as s on s.name = t.name
cross join newest_snapshot as n
