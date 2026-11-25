{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Data center hearing leads and whether their official page backs them up (#955).
    Grain: one row per lead (int_data_center_hearing_lead: the curated seed plus the CC BY
    tracker leads, #956).

    A lead is a claimed upcoming meeting from research lists. It is VERIFIED only when its
    official government page (fetched by ingestion.data_centers.fetch_hearing_sources into
    bronze_data_center_hearing_source) states the claimed date TOGETHER WITH a data center
    word (data_center_regex, the site-wide test):
      * a web page: a data center word within ~500 characters of a statement of the date (the
        same section of the page). Topic pages always say "data center" somewhere, so a
        date anywhere on the page (a sidebar calendar, another deadline) is not enough (#961).
      * a PDF agenda: the agenda IS the meeting, so the date anywhere on it plus a data center
        word anywhere on it is enough.
    The date may be written out with a capital ("December 1", "DEC. 1st"; lowercase prose like
    "may 3" doesn't count) or numeric ("12/01/2026", "12-1-26", "2026-12-01"). A written date
    followed by a DIFFERENT year ("December 1, 2025") does not count; no year at all is fine,
    agendas often omit it.
    Only verified rows are served (data_center_hearing_verified); every other status says what
    is missing, so the gaps are visible instead of being filled with a guess (CLAUDE.md, No
    Fabricated Data).

    status, first that applies:
      unsourced                no official URL (a tracker, a news report, or nothing)
      not_fetched              official URL, not fetched yet
      fetch_failed             fetched, but nothing read (robots.txt, HTTP error, bot check, scanned PDF)
      no_data_center_mention   the page doesn't say a data center word
      date_not_found           the page doesn't state the claimed date
      date_not_with_item       a web page states the date, but nowhere near a data center word
      verified                 the date and the data center item together
    evidence: verbatim text of the official page with whole data center phrases in <mark>:
    the date's passage (250 characters each side), and when it doesn't say the words, " … " then
    the nearest data center passage of the same region (web page) or of the agenda (PDF).
    Trimmed to whole words. Null unless verified.
    tentative: the evidence window says tentative / expected / not final / to be determined.
    jurisdiction_id: the jurisdiction whose name and state match the lead exactly once; null when
    none or several match (never a guess).
    Design: web_docs/docs/development/data-center-hearings.md
*/

{%- set dc_regex = data_center_regex() %}

with leads as (
    select * from {{ ref('int_data_center_hearing_lead') }}
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
        coalesce(p.content_type, '') ilike '%pdf%'                  as is_pdf,
        nullif(btrim(p.page_text), '')                              as page_text,
        p.lead_id is not null                                       as was_fetched,
        -- the claimed date. Written out, capitalised (December / DECEMBER / Dec / DEC, and Sept),
        -- matched case-sensitively so prose like "may 3" doesn't count; not followed by a
        -- different year. Or numeric: 12/01/2026, 12-1-26, 12.01.2026, or ISO 2026-12-01.
        '(?:\m(?:' || to_char(l.meeting_date, 'FMMonth') || '|' || upper(to_char(l.meeting_date, 'FMMonth'))
            || '|' || to_char(l.meeting_date, 'Mon') || '|' || upper(to_char(l.meeting_date, 'Mon'))
            || case when extract(month from l.meeting_date) = 9 then '|Sept|SEPT' else '' end
            || ')\.?,?\s*0?' || extract(day from l.meeting_date)::int || '(?:st|nd|rd|th)?\M'
            || '(?!,?\s*(?!' || to_char(l.meeting_date, 'YYYY') || ')(?:19|20)\d\d\M)'
            || '|\m0?' || extract(month from l.meeting_date)::int || '[/.-]0?' || extract(day from l.meeting_date)::int
            || '[/.-](?:20)?' || to_char(l.meeting_date, 'YY') || '\M'
            || '|' || to_char(l.meeting_date, 'YYYY-MM-DD') || ')'     as date_re
    from leads as l
    left join pages as p on p.lead_id = l.lead_id
),

windows as (
    -- every statement of the date on the page: `region` is up to ~500 characters on each side
    -- (two chained {0,250}: Postgres caps one repeat at 255), `pre`/`post` the 250 nearest
    select d.lead_id, w.n, w.m[1] as region_before, w.m[2] as date_text, w.m[3] as region_after
    from date_patterns as d
    cross join lateral regexp_matches(
        coalesce(d.page_text, ''),
        '([\s\S]{0,250}[\s\S]{0,250})(' || d.date_re || ')([\s\S]{0,250}[\s\S]{0,250})', 'g'
    ) with ordinality as w(m, n)
),

shaped as (
    select
        lead_id,
        n,
        -- the date's own passage: 250 characters each side
        right(region_before, 250) || date_text || left(region_after, 250)                   as date_window,
        region_before || date_text || region_after                                          as region
    from windows
),

first_windows as (
    select
        lead_id,
        (array_agg(date_window order by n))[1]                                              as date_window,
        -- the first statement of the date with a data center word in its region
        (array_agg(date_window order by n) filter (where region ~* '\y{{ dc_regex }}\y'))[1] as item_date_window,
        (array_agg(region order by n) filter (where region ~* '\y{{ dc_regex }}\y'))[1]      as item_region
    from shaped
    group by lead_id
),

checked as (
    select
        d.*,
        coalesce(d.page_text, '') ~* '\y{{ dc_regex }}\y'                                   as says_data_center,
        fw.date_window is not null                                                          as states_date,
        fw.item_region is not null or (d.is_pdf and fw.date_window is not null)             as date_with_item,
        -- the evidence, before marking and trimming: the date's passage; when that passage
        -- doesn't say the words, then the nearest data center passage of the same region (web
        -- page) or of the agenda (PDF), after " … "
        case
            when fw.item_region is not null and fw.item_date_window ~* '\y{{ dc_regex }}\y' then fw.item_date_window
            when fw.item_region is not null then
                regexp_replace(fw.item_date_window, '\s\S*$', '') || ' … ' ||
                regexp_replace(regexp_replace((regexp_match(fw.item_region, '([\s\S]{0,160}\y{{ dc_regex }}\y[\s\S]{0,160})', 'i'))[1], '^\S*\s', ''), '\s\S*$', '')
            when d.is_pdf and fw.date_window is not null then
                regexp_replace(fw.date_window, '\s\S*$', '') || ' … ' ||
                regexp_replace(regexp_replace((regexp_match(d.page_text, '([\s\S]{0,160}\y{{ dc_regex }}\y[\s\S]{0,160})', 'i'))[1], '^\S*\s', ''), '\s\S*$', '')
        end                                                                                 as raw_evidence
    from date_patterns as d
    left join first_windows as fw on fw.lead_id = d.lead_id
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
        when not c.date_with_item then 'date_not_with_item'
        else 'verified'
    end)::text                                                          as status,
    c.fetch_error::text                                                 as fetch_error,
    -- verbatim window, partial words trimmed at both ends, whole data center phrases marked
    (case when c.date_with_item and c.says_data_center then
        regexp_replace(
            regexp_replace(regexp_replace(btrim(regexp_replace(c.raw_evidence, '\s+', ' ', 'g')), '^\S*\s', ''), '\s\S*$', ''),
            '\y({{ dc_regex }})\y', '<mark>\1</mark>', 'gi'
        )
    end)::text                                                          as evidence,
    coalesce(c.date_with_item and c.raw_evidence ~* '\m(tentative(ly)?|expected|not final|to be determined|tbd)\M', false)::boolean as tentative,
    c.fetched_at::timestamptz                                           as checked_at
from checked as c
left join juris as j on j.lead_id = c.lead_id
