/*
    Data center items on meeting agendas (DC-4.2, #250).
    Grain: one row per agenda document that mentions a data center.

    Agendas come from event_meeting_document (document_type = 'agenda', extracted PDF
    text in content). Agendas are posted before the meeting, so a future doc_date is
    an item residents can still attend; the API works out upcoming vs past from today.

    evidence is a verbatim ts_headline excerpt with the matched words in <mark> (the
    site-wide "show the match evidence" rule); a document whose text doesn't produce
    one isn't kept. mentions_zoning_or_utility is true when a zoning, land-use, tax
    incentive or utility word sits within ~250 characters of a data center mention.
    data_center_site_id links a tracked site when the agenda names it (site name or
    project of 6+ characters) in the same state; otherwise null.
*/

{%- set dc_regex = "(data[ -]?cent(er|re)s?|hyperscale|server farms?)" -%}
{%- set context_regex = "(rezon|zoning|zoned|annex|variance|special use|conditional use|site plan|land use|abatement|incentive|pilot agreement|payment in lieu|tax|water|sewer|wastewater|utilit|electric|substation|transmission|power)" %}

with agendas as (
    select
        d.event_meeting_document_id,
        d.jurisdiction_id,
        d.state_code,
        d.state,
        d.body_name,
        d.meeting_title,
        d.doc_date,
        d.document_url,
        d.content
    from {{ ref('event_meeting_document') }} as d
    where d.document_type = 'agenda'
      and d.content is not null
      and d.content ~* '\y{{ dc_regex }}\y'
),

with_evidence as (
    select
        a.*,
        ts_headline(
            'english',
            a.content,
            to_tsquery('english', 'data <-> center | data <-> centre | hyperscale | server <-> farm'),
            'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=35, MinWords=12, FragmentDelimiter=" … "'
        ) as evidence,
        (
            a.content ~* '{{ dc_regex }}.{0,250}{{ context_regex }}'
            or a.content ~* '{{ context_regex }}.{0,250}{{ dc_regex }}'
        ) as mentions_zoning_or_utility
    from agendas as a
),

site_names as (
    select data_center_site_id, state_code, lower(site_name) as phrase, site_name
    from {{ ref('data_center_site') }}
    where state_code is not null and length(site_name) >= 6
    union all
    select data_center_site_id, state_code, lower(project) as phrase, site_name
    from {{ ref('data_center_site') }}
    where state_code is not null and length(project) >= 6
),

site_match as (
    select distinct on (e.event_meeting_document_id)
        e.event_meeting_document_id,
        s.data_center_site_id
    from with_evidence as e
    inner join site_names as s
        on s.state_code = e.state_code
       and position(s.phrase in lower(e.content)) > 0
    order by e.event_meeting_document_id, length(s.phrase) desc, s.site_name
),

known_jurisdictions as (
    select jurisdiction_id, name as jurisdiction_name
    from {{ ref('jurisdictions') }}
)

select
    e.event_meeting_document_id::text                 as data_center_agenda_item_id,
    e.event_meeting_document_id::text                 as event_meeting_document_id,
    j.jurisdiction_id::text                           as jurisdiction_id,
    j.jurisdiction_name::text                         as jurisdiction_name,
    e.state_code::text                                as state_code,
    e.state::text                                     as state,
    e.body_name::text                                 as body_name,
    e.meeting_title::text                             as meeting_title,
    e.doc_date::date                                  as doc_date,
    e.document_url::text                              as document_url,
    e.mentions_zoning_or_utility::boolean             as mentions_zoning_or_utility,
    e.evidence::text                                  as evidence,
    m.data_center_site_id::text                       as data_center_site_id
from with_evidence as e
left join known_jurisdictions as j on j.jurisdiction_id = e.jurisdiction_id
left join site_match as m on m.event_meeting_document_id = e.event_meeting_document_id
where e.evidence like '%<mark>%'
