{{ config(materialized='view', tags=['staging', 'meetings', 'documents', 'platform_meetings']) }}

/*
staging.stg_platform_meeting_documents — the agenda and minutes of Granicus / Legistar
meetings (#536), in the shape event_meeting_document unions. Grain: one row per
document (jurisdiction_id, url_sha256).

One row per agenda_url / minutes_url of a meeting that has a jurisdiction and a date.
content is the text the platform serves through its API (Legistar agenda items and
minutes notes), not PDF extraction: the PDFs sit on hosts whose robots.txt disallows
crawlers. A document with no served text keeps content NULL (still searchable on its
title and body).

event_meeting_document_id uses the same md5(jurisdiction_id || '|' || url_sha256)
surrogate as the SuiteOne and homepage-crawl models. Legistar PDF URLs are on
legistar*.com / legistar*.granicus.com hosts, which neither of those models reads, so
the three stay disjoint; the distinct on guards the grain anyway.
*/

with docs as (

    select
        m.jurisdiction_id,
        m.census_geoid,
        m.state_code,
        m.state,
        d.document_type,
        d.document_url,
        d.content,
        m.meeting_date                                       as doc_date,
        coalesce(m.title, m.body_name)                       as meeting_title,
        {{ normalize_meeting_body_key('coalesce(m.body_name, m.title)') }} as body_key,
        m.platform                                           as source,
        m.fetched_at
    from {{ ref('stg_bronze_platform_meeting') }} as m
    cross join lateral (
        values
            ('agenda'::text,  m.agenda_url,  m.agenda_text),
            ('minutes'::text, m.minutes_url, m.minutes_text)
    ) as d(document_type, document_url, content)
    where d.document_url is not null
      and m.jurisdiction_id is not null
      and m.meeting_date is not null

),

keyed as (

    select
        md5(jurisdiction_id || '|' || encode(sha256(convert_to(document_url, 'UTF8')), 'hex')) as event_meeting_document_id,
        jurisdiction_id,
        census_geoid,
        encode(sha256(convert_to(document_url, 'UTF8')), 'hex') as url_sha256,
        state_code,
        state,
        document_type,
        document_url,
        doc_date,
        meeting_title,
        body_key,
        content,
        source,
        fetched_at::timestamp                                as created_at
    from docs

)

select distinct on (event_meeting_document_id) *
from keyed
order by event_meeting_document_id, created_at desc
