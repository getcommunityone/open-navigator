-- #525: the quote shown for a company named from a meeting is the transcript's own words.
-- Strip the <mark> tags and the "… " / " …" cut markers from the evidence; what is left must
-- sit inside the passage text it came from. Any row returned is a quote that is not verbatim.
with quotes as (
    select
        c.decision_company_mention_id,
        c.data_center_meeting_mention_id,
        regexp_replace(
            regexp_replace(replace(replace(c.evidence, '<mark>', ''), '</mark>', ''), '^… ', ''),
            ' …$', ''
        ) as quote
    from {{ ref('decision_company_mention') }} as c
    where c.evidence_source = 'meeting_passage'
)

select q.decision_company_mention_id, q.data_center_meeting_mention_id, q.quote
from quotes as q
left join {{ ref('data_center_meeting_mention') }} as mm
    on mm.data_center_meeting_mention_id = q.data_center_meeting_mention_id
left join {{ ref('int_data_center_transcript__passage') }} as p
    on p.video_id = mm.video_id and p.passage_index = mm.passage_index
where p.passage_text is null
   or position(q.quote in p.passage_text) = 0
