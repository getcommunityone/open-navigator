{{
    config(
        materialized='table',
        tags=['intermediate', 'browse', 'transcripts', 'cause', 'keyword-fts'],
        post_hook=[
            "create index if not exists {{ this.name }}_cause_idx on {{ this }} (cause_id)",
            "create index if not exists {{ this.name }}_video_idx on {{ this }} (video_id)"
        ]
    )
}}

/*
int_transcript_keyword_cause — pure-SQL/dbt full-text CAUSE tagging of the FULL
transcript universe (~119k videos). The cause sibling of
int_transcript_keyword_topic.

WHY: causes had ZERO transcript coverage on the homepage Browse cards. The
existing keyword path (int_meeting_cause -> meeting_cause_link) is keyed on
event_meeting_id, which only exists for the ~6k AI-analyzed videos, so it never
reached the ~119k transcript universe. This model matches the SAME curated
EveryOrg cause keyword vocabulary (kept identical to int_meeting_cause for
consistency) against gold.event_documents.content_tsv directly.

NO LLM. Reuses gold.event_documents.content_tsv (populated for all transcript
videos) + its existing GIN index — no new tsvector/index built.

GRAIN: one row per (video_id, cause_id) — DISTINCT — carrying the place's
state_code + jurisdiction_name. Stamped link_type='transcript_keyword' by the
consuming mart so it is HONESTLY distinguishable from any AI-derived tag (these
are high-recall keyword hits — CLAUDE.md No Fabricated Data).

PRECISION STRATEGY (spot-checked): the EveryOrg cause vocabulary is mostly
single generic words ("school", "health", "youth"), so we REQUIRE >= 2 DISTINCT
keyword hits per (video, cause). One generic word is not a cause; two distinct
cause-vocabulary terms co-occurring is a defensible signal. Multi-word phrases
are matched as phrase queries; single words via plainto. Eyeballed
mental-health/education samples: on-topic at this threshold.

KEYWORD VOCABULARY: kept byte-for-byte in sync with int_meeting_cause's
cause_keyword VALUES list (editorial civic vocabulary, NOT fabricated counts).
If you edit one, edit both.

INJECTION SAFETY: each keyword goes through plainto_tsquery / phraseto_tsquery
('english', <kw>); no raw keyword text becomes a tsquery operator.

SOURCE : stg_everyorg__cause (cause id/name/icon/rank), event_documents
         (transcript, content_tsv, state_code, jurisdiction_name — read directly
         to avoid a DAG cycle with int_browse_entity_transcripts, which consumes
         this model).
TARGET : gold.int_transcript_keyword_cause (consumed by
         int_browse_entity_transcripts).
*/

-- Curated EveryOrg cause keyword vocabulary — KEEP IN SYNC with int_meeting_cause.
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

-- Sanitize each keyword to a tsquery (phraseto for multi-word ordered match,
-- plainto for single words). Drop keywords that sanitize to empty (stop-words).
cause_query as (
    select
        ck.cause_id,
        ck.keyword,
        nullif(
            case
                when array_length(regexp_split_to_array(trim(ck.keyword), '\s+'), 1) >= 2
                    then phraseto_tsquery('english', ck.keyword)::text
                else plainto_tsquery('english', ck.keyword)::text
            end,
            ''
        ) as pq
    from cause_keyword ck
),

valid_query as (
    select cause_id, keyword, pq from cause_query where pq is not null
),

cause_meta as (
    select cause_id, cause_name, icon, popularity_rank
    from {{ ref('stg_everyorg__cause') }}
),

transcript_place as (
    select distinct on (d.video_id)
        d.video_id,
        d.jurisdiction_name,
        d.state_code
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.state_code is not null
    order by d.video_id, d.content_length desc nulls last
),

doc as (
    select distinct on (d.video_id)
        d.video_id, d.content_tsv
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
),

phrase_hit as (
    select
        d.video_id,
        vq.cause_id,
        vq.keyword
    from doc d
    join valid_query vq
        on d.content_tsv @@ vq.pq::tsquery
),

scored as (
    select
        video_id,
        cause_id,
        count(distinct keyword) as n_keyword_hits
    from phrase_hit
    group by video_id, cause_id
)

select distinct
    s.video_id::text            as video_id,
    s.cause_id::text            as cause_id,
    cm.cause_name::text         as cause_name,
    cm.icon::text               as icon,
    cm.popularity_rank          as popularity_rank,
    tp.state_code::text         as state_code,
    tp.jurisdiction_name::text  as jurisdiction_name,
    s.n_keyword_hits::integer   as n_keyword_hits
from scored s
join transcript_place tp
    on tp.video_id = s.video_id
join cause_meta cm
    on cm.cause_id = s.cause_id
where s.n_keyword_hits >= 2
