{{ config(materialized='table', tags=['marts', 'business', 'serving']) }}

/*
    Where a meeting or a decision names a business (#1089, #1088; design: businesses-search.md).
    Grain: one row per business per record that names it (source_kind_code, source_record_id).

    source_kind_code:
      meeting   source_record_id is the recording's video_id. Fed by topic_company_mention (meeting rows) and by the
                meeting analysis's extracted organizations, whose quote is found in the meeting's own transcript.
      decision  source_record_id is event_decision_id. Fed by topic_company_mention (decision rows).
    Bills and ballot measures join later (#1090).

    quote_text is verbatim text of the record that names the business, cut to about 300 characters around the name
    (whitespace collapsed); a mention with no quote is not in this table. The place (state_code, jurisdiction_name,
    city) is the meeting's or decision's, and decides where the business shows. See int_business_mention__source for
    how each source is read.
*/

select
    md5(b.business_id || '|' || b.source_kind_code || '|' || b.source_record_id)::text as business_mention_id,
    b.business_id::text                                                  as business_id,
    b.source_kind_code::text                                             as source_kind_code,
    b.source_record_id::text                                             as source_record_id,
    b.source_url::text                                                   as source_url,
    b.mention_date::date                                                 as mention_date,
    b.state_code::text                                                   as state_code,
    b.jurisdiction_name::text                                            as jurisdiction_name,
    b.city::text                                                         as city,
    b.quote_text::text                                                   as quote_text
from {{ ref('int_business_mention__source') }} as b
inner join {{ ref('business') }} as biz on biz.business_id = b.business_id
