{{
    config(
        materialized='table',
        tags=['intermediate', 'civic', 'meeting-browse', 'cause']
    )
}}

/*
int_meeting_cause — full-text match of EveryOrg causes against meeting
transcripts. The cause↔meeting linkage that previously did NOT exist in the
warehouse (the frontend showed an empty state for causes); this builds it the
same way topics are matched in int_meeting_topic_civicsearch.

GRAIN: one row per (event_meeting_id, cause_id) where the meeting's transcript
full-text-matches the cause's curated keyword set.

WHY: EveryOrg causes (bronze.bronze_everyorg_causes) carry only a name +
description, no keyword vocabulary, so there is nothing to tag transcripts with
directly. This model supplies a curated, civic-relevant keyword set per cause
(the cause_keyword VALUES list below — editorial vocabulary, NOT fabricated
counts), ORs each cause's keywords into one tsquery, and tests it against the
meeting transcript's content_tsv (reusing the existing gold.event_documents GIN
index, event_documents_content_tsv_idx).

INJECTION SAFETY: identical to int_meeting_topic_civicsearch — each keyword goes
through plainto_tsquery('english', <kw>) (which sanitizes free text and ANDs
multi-word phrases into lexemes), and those sanitized fragments are ORed with
' | '. No raw keyword text ever becomes a tsquery operator.

SOURCE : bronze.bronze_everyorg_causes (cause id/name/icon/rank), event_meeting,
         event_documents (transcript, content_tsv).
TARGET : gold.int_meeting_cause (intermediate; consumed by meeting_cause_link).
*/

-- Curated, civic-relevant keyword vocabulary per EveryOrg cause. One row per
-- (cause_id, keyword). Keywords are matched against meeting transcripts; they are
-- editorial terms (real vocabulary), and every count downstream derives from a
-- genuine transcript match — nothing is hard-coded.
with cause_keyword(cause_id, keyword) as (
    select * from (values
        ('animals', 'animal'), ('animals', 'animals'), ('animals', 'pet'),
        ('animals', 'pets'), ('animals', 'animal shelter'), ('animals', 'wildlife'),
        ('animals', 'veterinary'), ('animals', 'leash'),

        ('arts', 'arts'), ('arts', 'culture'), ('arts', 'cultural'),
        ('arts', 'museum'), ('arts', 'theater'), ('arts', 'theatre'),
        ('arts', 'mural'), ('arts', 'gallery'), ('arts', 'public art'),

        ('climate', 'climate'), ('climate', 'emissions'), ('climate', 'greenhouse gas'),
        ('climate', 'carbon'), ('climate', 'sustainability'), ('climate', 'resilience'),
        ('climate', 'renewable energy'), ('climate', 'solar'),

        ('disasters', 'disaster'), ('disasters', 'emergency'), ('disasters', 'hurricane'),
        ('disasters', 'tornado'), ('disasters', 'flood'), ('disasters', 'fema'),
        ('disasters', 'evacuation'), ('disasters', 'disaster relief'),

        ('education', 'education'), ('education', 'school'), ('education', 'schools'),
        ('education', 'student'), ('education', 'students'), ('education', 'teacher'),
        ('education', 'classroom'), ('education', 'curriculum'), ('education', 'literacy'),

        ('environment', 'environment'), ('environment', 'environmental'),
        ('environment', 'pollution'), ('environment', 'conservation'),
        ('environment', 'recycling'), ('environment', 'wetland'),
        ('environment', 'watershed'), ('environment', 'habitat'),

        ('foodbanks', 'food bank'), ('foodbanks', 'hunger'),
        ('foodbanks', 'food insecurity'), ('foodbanks', 'food pantry'),
        ('foodbanks', 'nutrition'), ('foodbanks', 'meals'),

        ('health', 'health'), ('health', 'healthcare'), ('health', 'hospital'),
        ('health', 'clinic'), ('health', 'medical'), ('health', 'public health'),
        ('health', 'vaccine'),

        -- "oral health" is a synonym for "dental health"; both map to dental-health.
        ('dental-health', 'dental health'), ('dental-health', 'oral health'),
        ('dental-health', 'dental'), ('dental-health', 'dentist'),
        ('dental-health', 'dental care'), ('dental-health', 'dental clinic'),
        ('dental-health', 'tooth decay'), ('dental-health', 'oral hygiene'),

        ('humanitarian', 'humanitarian'), ('humanitarian', 'refugee'),
        ('humanitarian', 'humanitarian aid'), ('humanitarian', 'displaced'),

        ('justice', 'justice'), ('justice', 'civil rights'), ('justice', 'equity'),
        ('justice', 'discrimination'), ('justice', 'police reform'),
        ('justice', 'reentry'),

        ('lgbt', 'lgbtq'), ('lgbt', 'lgbt'), ('lgbt', 'transgender'),
        ('lgbt', 'pride'),

        ('mental-health', 'mental health'), ('mental-health', 'suicide'),
        ('mental-health', 'counseling'), ('mental-health', 'behavioral health'),
        ('mental-health', 'addiction'), ('mental-health', 'substance abuse'),

        ('religion', 'church'), ('religion', 'faith'), ('religion', 'religious'),
        ('religion', 'congregation'), ('religion', 'ministry'), ('religion', 'worship'),

        ('seniors', 'senior'), ('seniors', 'seniors'), ('seniors', 'elderly'),
        ('seniors', 'aging'), ('seniors', 'retirement'), ('seniors', 'medicare'),

        ('water', 'drinking water'), ('water', 'wastewater'), ('water', 'sewer'),
        ('water', 'watershed'), ('water', 'stormwater'), ('water', 'clean water'),

        ('women', 'women'), ('women', 'gender'), ('women', 'maternal'),
        ('women', 'domestic violence'),

        ('youth', 'youth'), ('youth', 'children'), ('youth', 'juvenile'),
        ('youth', 'after-school'), ('youth', 'childcare'), ('youth', 'recreation')
    ) as v(cause_id, keyword)
),

-- One OR-tsquery per cause, built injection-safe from its keyword set. Drop
-- keywords that sanitize to empty (stop-words only) so they don't break
-- to_tsquery.
cause_query as (
    select
        c.cause_id,
        c.cause_name,
        c.icon,
        c.popularity_rank,
        to_tsquery(
            'english',
            string_agg(distinct nullif(plainto_tsquery('english', k.keyword)::text, ''), ' | ')
        ) as ts_query
    from {{ ref('stg_everyorg__cause') }} c
    join cause_keyword k
        on k.cause_id = c.cause_id
    group by c.cause_id, c.cause_name, c.icon, c.popularity_rank
    having string_agg(distinct nullif(plainto_tsquery('english', k.keyword)::text, ''), ' | ') is not null
),

-- One transcript tsvector per meeting (collapse duplicate transcript docs for the
-- same video_id to a single row so the cause match is DISTINCT per meeting).
meeting_transcript as (
    select distinct on (m.event_meeting_id)
        m.event_meeting_id,
        d.content_tsv
    from {{ ref('event_meeting') }} m
    join {{ ref('event_documents') }} d
        on d.video_id = m.video_id
       and d.document_type = 'transcript'
    where m.video_id is not null
      and d.content_tsv is not null
    order by m.event_meeting_id, d.content_length desc nulls last
)

select
    mt.event_meeting_id,
    cq.cause_id,
    cq.cause_name,
    cq.icon,
    cq.popularity_rank
from meeting_transcript mt
join cause_query cq
    on mt.content_tsv @@ cq.ts_query
