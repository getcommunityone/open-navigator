{{ config(materialized='table', tags=['intermediate', 'business', 'serving-feed']) }}

/*
    Every place a meeting or decision names a business (#1089, design: businesses-search.md).
    Grain: one row per (business candidate, source_kind_code, source_record_id). The marts business and
    business_mention are built from it, so the typing and the quote rules live in one place.

    Which source feeds which source_kind_code:

      meeting   (a) topic_company_mention, mention_kind = 'meeting': the companies each topic names (data centers,
                    short-term rentals, license-plate readers, guns), each with a verbatim transcript excerpt;
                (b) the organizations the meeting analysis extracts (bronze_events_analysis_ai
                    structured_analysis -> 'organizations'), one row per organization per analysis. The analysis
                    carries no quote of its own (bronze_organizations_from_ai is aggregated per organization and keeps
                    only a role_in_meeting summary, which is the model's wording, not the record's), so the quote is
                    found in the meeting's own transcript (event_documents.content, by video_id): the first place the
                    name appears, case-insensitively, as written. A name that does not appear in the transcript
                    (the analysis also reads agendas and minutes) has no quote and is dropped: no quote, no mention.
      decision  topic_company_mention, mention_kind = 'decision'. It already carries the data-center decisions
                (decision_company_mention), the short-term-rental decisions and the seeded topics' decisions, each with
                a verbatim excerpt of the decision's headline and statement.

    Left out: organizations whose canonical type (canonical_org_type, or the organization master's own type) is
    government or political, since those are government bodies and political committees, not businesses.

    quote_text is the source excerpt with the <mark> tags removed, cut to about 300 characters around the first match.
    name_key is normalize_org_name(name), the key used to match the organization master and to count states.
    business_id is master_org_id when the name matched the organization master (by EIN, else by name_key and state),
    else md5(name_key | state_code); a topic company outside the master has no single state, so its state part is empty.
*/

with topic_rows as (
    select
        c.company_name                                                       as business_name,
        {{ normalize_org_name('c.company_name') }}                           as name_key,
        c.master_org_id,
        null::text                                                           as ein,
        'business'::text                                                     as org_type_code,
        true                                                                 as is_topic_company,
        (c.topic_query_id = 'data-centers')                                  as is_data_center_company,
        m.mention_kind                                                       as source_kind_code,
        coalesce(m.event_decision_id, m.video_id)                            as source_record_id,
        m.url                                                                as source_url,
        m.event_date::date                                                   as mention_date,
        m.state_code,
        m.jurisdiction_name,
        coalesce(dd.city, dc.city)                                           as city,
        m.evidence                                                           as raw_excerpt
    from {{ ref('topic_company_mention') }} as m
    inner join {{ ref('topic_company') }} as c on c.topic_company_id = m.topic_company_id
    left join {{ ref('event_decision') }} as dd
        on m.mention_kind = 'decision' and dd.event_decision_id::text = m.event_decision_id
    left join (
        select distinct on (video_id) video_id, city
        from {{ ref('event_documents') }}
        where video_id is not null
        order by video_id, event_document_id
    ) as dc on m.mention_kind = 'meeting' and dc.video_id = m.video_id
    where m.mention_kind in ('meeting', 'decision')
),

analyses as (
    select
        a.id                                   as analysis_id,
        jsonb_array_elements(a.structured_analysis -> 'organizations') as org
    from {{ source('bronze', 'bronze_events_analysis_ai') }} as a
    where a.structured_analysis is not null
      and {{ is_publishable_governance_analysis('a.structured_analysis') }}
      and jsonb_typeof(a.structured_analysis -> 'organizations') = 'array'
),

ai_orgs as (
    select
        x.analysis_id,
        btrim(x.org ->> 'org_name')                                          as org_name,
        nullif(regexp_replace(coalesce(x.org ->> 'ein', ''), '[^0-9]', '', 'g'), '') as ein,
        {{ canonical_org_type("x.org ->> 'org_type'", 'business') }}         as org_type_code,
        upper(substring(x.org ->> 'org_id' from '_([a-z]{2})$'))             as org_state_code
    from analyses as x
    where nullif(btrim(x.org ->> 'org_name'), '') is not null
      and length(btrim(x.org ->> 'org_name')) >= 4
),

meeting_docs as (
    select distinct on (d.video_id)
        d.video_id, d.content, d.event_date, d.state_code, d.jurisdiction_name, d.city, d.video_url
    from {{ ref('event_documents') }} as d
    inner join {{ ref('event_meeting') }} as em on em.video_id = d.video_id
    where d.video_id is not null and d.content is not null
      and em.event_meeting_id in (select analysis_id from ai_orgs)
    order by d.video_id, d.event_document_id
),

ai_meeting as (
    select
        o.org_name, o.ein, o.org_type_code, o.org_state_code,
        {{ normalize_org_name('o.org_name') }}  as name_key,
        em.video_id,
        d.event_date::date                      as mention_date,
        d.state_code,
        d.jurisdiction_name,
        d.city,
        d.video_url,
        strpos(lower(d.content), lower(o.org_name)) as pos,
        d.content
    from ai_orgs as o
    inner join {{ ref('event_meeting') }} as em on em.event_meeting_id = o.analysis_id
    inner join meeting_docs as d on d.video_id = em.video_id
    where o.org_type_code not in ('government', 'political')
),

ai_quoted as (
    select
        m.*,
        -- about 300 characters, verbatim, around the first place the name appears
        substr(m.content, greatest(1, m.pos - 150), 300) as quote_raw
    from ai_meeting as m
    where m.pos > 0
),

ai_matched as (
    select
        q.*,
        coalesce(by_ein.master_org_id, by_name.master_org_id)                as master_org_id,
        coalesce(by_ein.org_type, by_name.org_type)                          as master_org_type
    from ai_quoted as q
    left join lateral (
        select o.master_org_id, o.org_type
        from {{ ref('mdm_organization') }} as o
        where q.ein is not null and o.ein = q.ein
        order by o.n_occurrences desc nulls last, o.master_org_id
        limit 1
    ) as by_ein on true
    left join lateral (
        select o.master_org_id, o.org_type
        from {{ ref('mdm_organization') }} as o
        where q.name_key is not null
          and o.org_name_norm = q.name_key
          and o.state_code = coalesce(q.org_state_code, q.state_code)
        order by (o.ein is not null) desc, o.n_occurrences desc nulls last, o.master_org_id
        limit 1
    ) as by_name on true
),

ai_rows as (
    select
        org_name                                                             as business_name,
        name_key,
        master_org_id,
        ein,
        org_type_code,
        false                                                                as is_topic_company,
        false                                                                as is_data_center_company,
        'meeting'::text                                                      as source_kind_code,
        video_id                                                             as source_record_id,
        case when video_id !~ ':' then coalesce(video_url, 'https://www.youtube.com/watch?v=' || video_id)
             else video_url end                                              as source_url,
        mention_date,
        state_code,
        jurisdiction_name,
        city,
        quote_raw                                                            as raw_excerpt,
        coalesce(org_state_code, state_code)                                 as business_state_code
    from ai_matched
    where coalesce(master_org_type, '') not in ('government', 'political')
),

unioned as (
    select t.*, null::text as business_state_code from topic_rows as t
    union all
    select * from ai_rows
),

cleaned as (
    select
        u.*,
        replace(replace(u.raw_excerpt, '<mark>', ''), '</mark>', '')         as clean_excerpt,
        greatest(1, strpos(u.raw_excerpt, '<mark>') - 150)                   as cut_from
    from unioned as u
    where nullif(btrim(u.raw_excerpt), '') is not null
      and u.source_record_id is not null
      and u.name_key is not null
)

select distinct on (business_id, source_kind_code, source_record_id)
    business_id,
    business_name,
    name_key,
    master_org_id,
    ein,
    org_type_code,
    is_topic_company,
    is_data_center_company,
    source_kind_code,
    source_record_id,
    source_url,
    mention_date,
    state_code,
    jurisdiction_name,
    city,
    business_state_code,
    quote_text
from (
    select
        coalesce(c.master_org_id, md5(c.name_key || '|' || coalesce(c.business_state_code, ''))) as business_id,
        c.business_name, c.name_key, c.master_org_id, c.ein, c.org_type_code,
        c.is_topic_company, c.is_data_center_company,
        c.source_kind_code, c.source_record_id, c.source_url, c.mention_date,
        c.state_code, c.jurisdiction_name, c.city, c.business_state_code,
        btrim(regexp_replace(
            case when strpos(c.raw_excerpt, '<mark>') > 0
                 then substr(c.clean_excerpt, c.cut_from, 300)
                 else substr(c.clean_excerpt, 1, 300) end,
            '\s+', ' ', 'g'))                                                as quote_text
    from cleaned as c
) as q
where nullif(quote_text, '') is not null
order by business_id, source_kind_code, source_record_id, mention_date desc nulls last, business_name
