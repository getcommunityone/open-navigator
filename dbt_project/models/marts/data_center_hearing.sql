{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Data center hearing leads and whether their official page backs them up (#955).
    Grain: one row per lead (seeds.data_center_hearing_lead).

    A lead is a claimed upcoming meeting from research lists. It is VERIFIED only when its
    official government page (fetched by ingestion.data_centers.fetch_hearing_sources into
    bronze_data_center_hearing_source) both
      * says a data center word (data_center_regex, the site-wide test), and
      * states the claimed meeting date, written out ("December 1", "Dec. 1st") or numeric
        ("12/01/2026", "12-1-26", "2026-12-01"). The year isn't required: agendas often omit it.
    Only verified rows are served as hearings; every other status says what is missing, so the
    gaps are visible instead of being filled with a guess (CLAUDE.md, No Fabricated Data).

    status, first that applies:
      unsourced               no official URL (a tracker, a news report, or nothing)
      not_fetched             official URL, not fetched yet
      fetch_failed            fetched, but nothing read (robots.txt, HTTP error, bot check, scanned PDF)
      no_data_center_mention  the page doesn't say a data center word
      date_not_found          the page doesn't state the claimed date
      verified                both
    evidence: verbatim text of the official page with data center words in <mark> (the site-wide
    match-evidence rule). For a lead whose page states the date, it is the passage around the
    date (up to ~240 characters each side, within one line), which is what shows the page
    announces this meeting; otherwise the page's data center passages. Null unless the page
    says a data center word.
    jurisdiction_id: the jurisdiction whose name and state match the lead exactly once; null when
    none or several match (never a guess).
    Design: web_docs/docs/development/data-center-hearings.md
*/

{%- set dc_regex = data_center_regex() %}

with leads as (
    select * from {{ ref('data_center_hearing_lead') }}
),

pages as (
    select * from {{ source('bronze', 'bronze_data_center_hearing_source') }}
),

date_patterns as (
    select
        l.*,
        p.fetched_at,
        p.http_status,
        p.error                                                     as fetch_error,
        nullif(btrim(p.page_text), '')                              as page_text,
        p.lead_id is not null                                       as was_fetched,
        -- the claimed date, written out: December 1 / Dec. 1st / Dec 01 (case-insensitive)
        '\m(?:' || to_char(l.meeting_date, 'FMMonth') || '|' || to_char(l.meeting_date, 'Mon')
            || case when extract(month from l.meeting_date) = 9 then '|Sept' else '' end
            || ')\.?,?\s+0?' || extract(day from l.meeting_date)::int || '(?:st|nd|rd|th)?\M' as written_re,
        -- numeric: 12/01/2026, 12-1-26, 12.01.2026, or ISO 2026-12-01
        '(?:\m0?' || extract(month from l.meeting_date)::int || '[/.-]0?' || extract(day from l.meeting_date)::int
            || '[/.-](?:20)?' || to_char(l.meeting_date, 'YY') || '\M|'
            || to_char(l.meeting_date, 'YYYY-MM-DD') || ')'          as numeric_re
    from leads as l
    left join pages as p on p.lead_id = l.lead_id
),

checked as (
    select
        d.*,
        coalesce(d.page_text, '') ~* '\y{{ dc_regex }}\y'           as says_data_center,
        (coalesce(d.page_text, '') ~* d.written_re or coalesce(d.page_text, '') ~ d.numeric_re) as states_date,
        -- the passage around the first place the page states the date: the evidence that this
        -- page announces THIS meeting (a page's first data center mention is often its menu)
        coalesce(
            (regexp_match(d.page_text, '([^\n]{0,240}' || d.written_re || '[^\n]{0,240})', 'i'))[1],
            (regexp_match(d.page_text, '([^\n]{0,240}' || d.numeric_re || '[^\n]{0,240})'))[1]
        )                                                           as date_passage
    from date_patterns as d
),

juris as (
    select
        c.lead_id,
        min(j.jurisdiction_id) as jurisdiction_id,
        count(*)              as matches
    from checked as c
    join {{ ref('jurisdictions') }} as j
        on j.state_code = c.state_code
        and j.jurisdiction_type in ('city', 'town', 'county')
        and lower(regexp_replace(coalesce(j.name, j.display_name), '\s+(city|town|village|township|charter township|county|borough|cdp)$', '', 'i'))
          = lower(regexp_replace(c.jurisdiction_name, '\s+(city|town|village|township|charter township|county|borough)$', '', 'i'))
        and (
            -- a county lead matches only a county, and a non-county lead never matches one
            (c.jurisdiction_name ~* '\mcounty$') = (j.jurisdiction_type = 'county')
        )
    group by c.lead_id
)

select
    c.lead_id::text                                                     as data_center_hearing_id,
    case when j.matches = 1 then j.jurisdiction_id end::text            as jurisdiction_id,
    c.meeting_date::date                                                as meeting_date,
    c.jurisdiction_name::text                                           as jurisdiction_name,
    c.state_code::text                                                  as state_code,
    ({{ state_code_to_name('c.state_code') }})::text                    as state,
    c.body_name::text                                                   as body_name,
    c.topic::text                                                       as topic,
    c.source_kind::text                                                 as source_kind,
    c.source_name::text                                                 as source_name,
    nullif(c.source_url, '')::text                                      as source_url,
    c.lead_from::text                                                   as lead_from,
    (case
        when c.source_kind <> 'official' or coalesce(c.source_url, '') = '' then 'unsourced'
        when not c.was_fetched then 'not_fetched'
        when c.page_text is null then 'fetch_failed'
        when not c.says_data_center then 'no_data_center_mention'
        when not c.states_date then 'date_not_found'
        else 'verified'
    end)::text                                                          as status,
    c.fetch_error::text                                                 as fetch_error,
    (case
        -- verified, the date passage itself names the data center item: that passage, marked
        when c.says_data_center and c.date_passage ~* '\y{{ dc_regex }}\y' then
            ts_headline('english', btrim(c.date_passage), {{ data_center_headline_tsquery() }},
                        'StartSel=<mark>, StopSel=</mark>, HighlightAll=true')
        -- verified, the date stands on its own line (PDF agendas): the date line, then the page's
        -- data center passage, both verbatim
        when c.says_data_center and c.date_passage is not null then
            btrim(c.date_passage) || ' … ' ||
            ts_headline('english', c.page_text, {{ data_center_headline_tsquery() }},
                        'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=35, MinWords=12')
        -- otherwise the page's data center passages, so the gap is visible
        when c.says_data_center then
            ts_headline('english', c.page_text, {{ data_center_headline_tsquery() }},
                        'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=35, MinWords=12, FragmentDelimiter=" … "')
    end)::text                                                          as evidence,
    c.fetched_at::timestamptz                                           as checked_at
from checked as c
left join juris as j on j.lead_id = c.lead_id
