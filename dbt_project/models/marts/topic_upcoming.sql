{{
  config(
    materialized='table',
    tags=['marts', 'topic', 'upcoming', 'serving'],
    indexes=[
      {'columns': ['topic_id', 'state_code', 'item_date'], 'type': 'btree'},
      {'columns': ['topic_slug', 'item_date'], 'type': 'btree'}
    ]
  )
}}

/*
    Mart: topic_upcoming (#1302) — what is coming up on a curated topic: scheduled meetings, public hearings (and,
    when a source has them, comment deadlines and dated bill actions), each with a real date and the evidence that
    ties it to the topic. Grain: one row per (topic_id, item_key).

    PK  topic_upcoming_id = md5(topic_id | item_key).
    FK  topic_id -> civicsearch_topic; platform_meeting_id -> platform_meeting; event_meeting_document_id ->
        event_meeting_document; data_center_hearing_id -> data_center_hearing; organization_event_id ->
        organization_event (each nullable but the first).

    Three ways an item is tied to a topic, never by guess (match_basis):

      agenda_text             a future agenda (event_meeting_document, doc_date on or after the build date) whose text
                              matches the topic's keyword phrases (civicsearch_topic.keyword_stats, the same phrases
                              topic_transcript_link uses). matched_text = ts_headline of the agenda with <mark>.
                              kind = hearing when the highlighted passage says "hearing", else meeting.
      official_notice         a data center hearing whose official page was fetched and states the date with the item
                              (data_center_hearing.status = 'verified'); data centers only. matched_text = the page's
                              own <mark>ed passage. kind = hearing.
      place_discussed_before  a scheduled meeting (a Legistar calendar row in platform_meeting, or a scheduled YouTube
                              livestream: duration 0, date from the title) of a government whose own recorded meeting
                              discussed the topic in the two years before the build. The agenda is not posted yet, so
                              the evidence is that earlier meeting's verbatim passage (topic_transcript_link
                              .evidence_passage), and prior_* name it. Meetings the AI reading marked as no real item
                              on the topic (keyword false hits) do not count. kind = meeting.

    Nothing else is added. Our OpenStates copy has no future-dated hearing or action on a topic bill, so no
    bill_action rows are built yet; the API lists still-open bills (topic_legislation_bill) separately, dated by their
    last action. Rule and coverage: web_docs/docs/development/topic-upcoming.md.

    Rows are kept from the build date on; the API shows only item_date >= today, so a row that has passed between
    builds is never shown as upcoming. source_updated_at = when the source row was last fetched; built_at = this build.
*/

{%- set hl_opts = "'MaxFragments=1, MinWords=10, MaxWords=32, StartSel=<mark>, StopSel=</mark>'" -%}

with

curated_topic as (
    select topic_id, query_id as topic_slug, keyword_stats
    from {{ ref('civicsearch_topic') }}
    where source = 'curated'
),

topic_query as (
    select
        t.topic_id,
        t.topic_slug,
        string_agg(distinct nullif(phraseto_tsquery('english', kw.elem)::text, ''), ' | ') as tsq
    from curated_topic as t
    cross join lateral jsonb_array_elements_text(t.keyword_stats) as kw(elem)
    group by t.topic_id, t.topic_slug
),

-- 1. Future agendas whose text names the topic.
agenda_match as (
    select
        q.topic_id,
        q.topic_slug,
        d.event_meeting_document_id,
        d.jurisdiction_id,
        d.state_code,
        d.state,
        d.body_name,
        d.meeting_title,
        d.doc_date,
        d.document_url,
        d.created_at,
        nullif(trim(ts_headline('english', d.content, to_tsquery('english', q.tsq), {{ hl_opts }})), '') as passage
    from {{ ref('event_meeting_document') }} as d
    inner join topic_query as q
        on d.content_tsv @@ to_tsquery('english', q.tsq)
    where d.doc_date >= current_date
      and d.document_type = 'agenda'
      and q.tsq is not null
),

agenda_items as (
    select
        a.topic_id,
        a.topic_slug,
        'agenda:' || a.event_meeting_document_id                                   as item_key,
        case when a.passage ~* 'hearing' then 'hearing' else 'meeting' end         as kind,
        'agenda_text'                                                               as match_basis,
        a.doc_date                                                                  as item_date,
        null::text                                                                  as item_time,
        a.jurisdiction_id,
        null::text                                                                  as jurisdiction_name,
        a.state_code,
        a.state,
        a.body_name,
        coalesce(nullif(trim(a.meeting_title), ''), a.body_name)                   as title,
        null::text                                                                  as location,
        a.document_url                                                              as source_url,
        'Agenda'                                                                    as source_label,
        a.passage                                                                   as matched_text,
        null::text                                                                  as prior_video_id,
        null::date                                                                  as prior_meeting_date,
        null::text                                                                  as prior_url,
        false                                                                       as tentative,
        null::text                                                                  as platform_meeting_id,
        a.event_meeting_document_id,
        null::text                                                                  as data_center_hearing_id,
        null::text                                                                  as organization_event_id,
        null::text                                                                  as host_org_name,
        null::text                                                                  as host_master_org_id,
        a.created_at::timestamptz                                                   as source_updated_at
    from agenda_match as a
    where a.passage like '%<mark>%'
      and a.document_url is not null
),

-- 2. Verified data center hearings (official page fetched, date stated with the item).
hearing_items as (
    select
        t.topic_id,
        t.topic_slug,
        'hearing:' || h.data_center_hearing_id                                      as item_key,
        'hearing'                                                                   as kind,
        'official_notice'                                                           as match_basis,
        h.meeting_date                                                              as item_date,
        null::text                                                                  as item_time,
        h.jurisdiction_id,
        h.jurisdiction_name,
        h.state_code,
        h.state,
        h.body_name,
        coalesce(nullif(trim(h.topic), ''), h.body_name)                           as title,
        null::text                                                                  as location,
        h.source_url,
        'Official notice'                                                           as source_label,
        h.evidence                                                                  as matched_text,
        null::text                                                                  as prior_video_id,
        null::date                                                                  as prior_meeting_date,
        null::text                                                                  as prior_url,
        coalesce(h.tentative, false)                                                as tentative,
        null::text                                                                  as platform_meeting_id,
        null::text                                                                  as event_meeting_document_id,
        h.data_center_hearing_id,
        null::text                                                                  as organization_event_id,
        null::text                                                                  as host_org_name,
        null::text                                                                  as host_master_org_id,
        h.checked_at                                                                as source_updated_at
    from {{ ref('data_center_hearing') }} as h
    inner join curated_topic as t
        on t.topic_slug = 'data-centers'
    where h.status = 'verified'
      and h.meeting_date >= current_date
      and h.source_url is not null
      and h.evidence like '%<mark>%'
),

-- 3. Scheduled meetings of governments that discussed the topic before.
youtube_video as (
    select distinct on (y.video_id)
        y.video_id,
        nullif(trim(y.jurisdiction_id), '')                                         as jurisdiction_id,
        nullif(trim(y.jurisdiction_name), '')                                       as jurisdiction_name,
        nullif(trim(y.state_code), '')                                              as state_code,
        nullif(trim(y.state), '')                                                   as state,
        y.title,
        y.event_date,
        y.event_time,
        y.video_url,
        y.duration_minutes,
        coalesce(y.last_updated, y.loaded_at)                                       as updated_at
    from {{ source('bronze', 'bronze_event_youtube') }} as y
    where y.video_id is not null
    order by y.video_id, coalesce(y.last_updated, y.loaded_at) desc nulls last
),

-- Keyword hits the AI reading found to hold no real item on the topic.
no_item as (
    select l.topic_id, l.video_id
    from {{ ref('topic_meeting_lean') }} as l
    where coalesce(l.excluded_no_item, false) or l.outcome_group = 'no_item'
    union
    select t.topic_id, d.video_id
    from {{ ref('data_center_meeting_lean') }} as d
    inner join curated_topic as t
        on t.topic_slug = 'data-centers'
    where coalesce(d.excluded_no_item, false) or d.dc_outcome = 'no_data_center_item'
),

prior_meeting as (
    select distinct on (k.topic_id, v.jurisdiction_id)
        k.topic_id,
        v.jurisdiction_id,
        k.jurisdiction_name,
        k.state_code,
        k.video_id,
        k.event_date,
        k.video_url,
        k.evidence_passage
    from {{ ref('topic_transcript_link') }} as k
    inner join youtube_video as v
        on v.video_id = k.video_id
    where v.jurisdiction_id is not null
      and k.event_date between current_date - 730 and current_date
      and k.evidence_passage like '%<mark>%'
      and not exists (
          select 1 from no_item as n where n.topic_id = k.topic_id and n.video_id = k.video_id
      )
    order by k.topic_id, v.jurisdiction_id, k.event_date desc, k.video_id
),

scheduled as (
    select
        'legistar:' || p.platform_meeting_id                                        as item_key,
        p.platform_meeting_id,
        p.jurisdiction_id,
        null::text                                                                  as jurisdiction_name,
        p.state_code,
        p.state,
        p.body_name,
        coalesce(nullif(trim(p.title), ''), p.body_name)                           as title,
        p.meeting_date                                                              as item_date,
        nullif(trim(p.meeting_time), '')                                            as item_time,
        nullif(trim(p.location), '')                                                as location,
        coalesce(p.agenda_url, p.detail_url)                                        as source_url,
        case when p.agenda_url is not null then 'Agenda' else 'Meeting page' end    as source_label,
        p.fetched_at::timestamptz                                                   as source_updated_at
    from {{ ref('platform_meeting') }} as p
    where p.meeting_date >= current_date
      and p.jurisdiction_id is not null
      and coalesce(p.agenda_url, p.detail_url) is not null
    union all
    select
        'youtube:' || v.video_id,
        null::text,
        v.jurisdiction_id,
        v.jurisdiction_name,
        v.state_code,
        v.state,
        null::text,
        v.title,
        v.event_date,
        -- A livestream's stored time is when the video was scheduled or published, not when the meeting starts.
        null::text,
        null::text,
        coalesce(v.video_url, 'https://www.youtube.com/watch?v=' || v.video_id),
        'Livestream',
        v.updated_at::timestamptz
    from youtube_video as v
    -- A livestream not yet held has no length; a dated title on a video that already has one is a typo, not a plan.
    where coalesce(v.duration_minutes, 0) = 0
      and v.event_date between current_date and current_date + 365
      and v.jurisdiction_id is not null
      -- A government meeting, not a ceremony, webinar or celebration the same channel streams.
      and v.title ~* '(meeting|session|council|commission|board|hearing|committee|assembly|supervisors|\mboc\M)'
      and v.title !~* '(ceremony|webinar|reflection|celebration|parade|holiday|tree lighting|awards?|graduation)'
),

place_items as (
    select
        pm.topic_id,
        t.topic_slug,
        s.item_key,
        'meeting'                                                                   as kind,
        'place_discussed_before'                                                    as match_basis,
        s.item_date,
        s.item_time,
        s.jurisdiction_id,
        coalesce(s.jurisdiction_name, pm.jurisdiction_name)                         as jurisdiction_name,
        coalesce(s.state_code, pm.state_code)                                       as state_code,
        s.state,
        s.body_name,
        s.title,
        s.location,
        s.source_url,
        s.source_label,
        pm.evidence_passage                                                         as matched_text,
        pm.video_id                                                                 as prior_video_id,
        pm.event_date                                                               as prior_meeting_date,
        coalesce(pm.video_url, 'https://www.youtube.com/watch?v=' || pm.video_id)   as prior_url,
        false                                                                       as tentative,
        s.platform_meeting_id,
        null::text                                                                  as event_meeting_document_id,
        null::text                                                                  as data_center_hearing_id,
        null::text                                                                  as organization_event_id,
        null::text                                                                  as host_org_name,
        null::text                                                                  as host_master_org_id,
        s.source_updated_at
    from scheduled as s
    inner join prior_meeting as pm
        on pm.jurisdiction_id = s.jurisdiction_id
    inner join curated_topic as t
        on t.topic_id = pm.topic_id
),

-- 4. Events a topic's nonprofits publish on their own websites (#1347): hosts tied to the topic by a meeting, their
--    990 mission or their name (not by IRS category alone). The evidence is the host's own tie to the topic.
org_event_items as (
    select
        o.topic_id,
        o.topic_slug,
        'org_event:' || e.organization_event_id                                     as item_key,
        'event'                                                                     as kind,
        'hosted_by_org'                                                             as match_basis,
        e.event_date                                                                as item_date,
        e.event_time                                                                as item_time,
        null::text                                                                  as jurisdiction_id,
        initcap(e.city)                                                             as jurisdiction_name,
        e.state_code,
        e.state,
        null::text                                                                  as body_name,
        e.title,
        e.location,
        e.event_url                                                                 as source_url,
        'Event page'                                                                as source_label,
        o.match_text                                                                as matched_text,
        null::text                                                                  as prior_video_id,
        null::date                                                                  as prior_meeting_date,
        null::text                                                                  as prior_url,
        false                                                                       as tentative,
        null::text                                                                  as platform_meeting_id,
        null::text                                                                  as event_meeting_document_id,
        null::text                                                                  as data_center_hearing_id,
        e.organization_event_id,
        e.org_name                                                                  as host_org_name,
        e.master_org_id                                                             as host_master_org_id,
        e.fetched_at                                                                as source_updated_at
    from {{ ref('organization_event') }} as e
    inner join {{ ref('topic_organization') }} as o
        on o.master_org_id = e.master_org_id
    where e.event_date >= current_date
      and o.evidence_rank <= 3
      and o.match_text like '%<mark>%'
),

unioned as (
    select *, 1 as basis_rank from agenda_items
    union all
    select *, 2 from hearing_items
    union all
    select *, 3 from place_items
    union all
    select *, 4 from org_event_items
),

-- One row per (topic, item): an agenda match beats the same meeting found by place.
deduped as (
    select distinct on (topic_id, item_key) *
    from unioned
    order by topic_id, item_key, basis_rank
),

-- The state's full name where a source carried only the code.
state_names as (
    select distinct on (state_code) state_code, state
    from {{ ref('topic_transcript_link') }}
    where state is not null and length(state) > 2
    order by state_code, state
)

select
    md5(d.topic_id::text || '|' || d.item_key)::text                                 as topic_upcoming_id,
    d.topic_id::integer                                                              as topic_id,
    d.topic_slug::text                                                               as topic_slug,
    d.item_key::text                                                                 as item_key,
    d.kind::text                                                                     as kind,
    d.match_basis::text                                                              as match_basis,
    d.item_date::date                                                                as item_date,
    d.item_time::text                                                                as item_time,
    d.jurisdiction_id::text                                                          as jurisdiction_id,
    d.jurisdiction_name::text                                                        as jurisdiction_name,
    d.state_code::text                                                               as state_code,
    coalesce(nullif(d.state, d.state_code), sn.state)::text                          as state,
    d.body_name::text                                                                as body_name,
    d.title::text                                                                    as title,
    d.location::text                                                                 as location,
    d.source_url::text                                                               as source_url,
    d.source_label::text                                                             as source_label,
    d.matched_text::text                                                             as matched_text,
    d.prior_video_id::text                                                           as prior_video_id,
    d.prior_meeting_date::date                                                       as prior_meeting_date,
    d.prior_url::text                                                                as prior_url,
    d.tentative::boolean                                                             as tentative,
    d.platform_meeting_id::text                                                      as platform_meeting_id,
    d.event_meeting_document_id::text                                                as event_meeting_document_id,
    d.data_center_hearing_id::text                                                   as data_center_hearing_id,
    d.organization_event_id::text                                                    as organization_event_id,
    d.host_org_name::text                                                            as host_org_name,
    d.host_master_org_id::text                                                       as host_master_org_id,
    d.source_updated_at::timestamptz                                                 as source_updated_at,
    now()::timestamptz                                                               as built_at
from deduped as d
left join state_names as sn
    on sn.state_code = d.state_code
where d.state_code is not null
