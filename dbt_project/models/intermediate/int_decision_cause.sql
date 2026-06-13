{{
    config(
        materialized='table',
        tags=['intermediate', 'browse', 'decisions', 'cause', 'keyword-fts'],
        post_hook=[
            "create index if not exists {{ this.name }}_cause_idx on {{ this }} (cause_id)",
            "create index if not exists {{ this.name }}_c1_event_idx on {{ this }} (c1_event_id)"
        ]
    )
}}

/*
int_decision_cause — pure-SQL/dbt full-text CAUSE tagging at the DECISION grain
(public.event_decision, ~8.9k rows, all carrying c1_event_id). The decision
sibling of int_transcript_keyword_cause.

WHY: the meeting browse for causes should link to DECISIONS first (a meeting's
decisions rolled up via c1_event_id), falling back to transcript keyword matches
only when a meeting has no decisions. This model is the decision leg: it matches
the SAME curated EveryOrg cause keyword vocabulary against the decision TEXT
(headline + decision_statement), NOT the AI primary_theme — a deliberate
keyword-match choice so the linkage is an honest, traceable keyword signal.

NO LLM. Matches lower(headline || ' ' || decision_statement)::tsvector against
each cause keyword's phraseto/plainto tsquery.

GRAIN: one row per (event_decision_id, cause_id) — DISTINCT. Carries c1_event_id
(for the meeting roll-up), cause_name, icon, popularity_rank.

PRECISION STRATEGY: identical threshold to int_transcript_keyword_cause — the
EveryOrg cause vocabulary is mostly single generic words ("school", "health"),
so we REQUIRE >= 2 DISTINCT keyword hits per (decision, cause). Decision text is
much shorter than a transcript, so two distinct cause-vocabulary terms
co-occurring in a single decision headline+statement is a strong signal.

KEYWORD VOCABULARY: kept byte-for-byte in sync with int_transcript_keyword_cause
(and int_meeting_cause). KEEP IN SYNC — if you edit one, edit all three.

INJECTION SAFETY: each keyword goes through plainto_tsquery / phraseto_tsquery
('english', <kw>); no raw keyword text becomes a tsquery operator.

SOURCE : stg_everyorg__cause (cause id/name/icon/rank), event_decision
         (headline, decision_statement, c1_event_id).
TARGET : gold.int_decision_cause (consumed by meeting_cause_link).
*/

-- Curated EveryOrg cause keyword vocabulary — KEEP IN SYNC with
-- int_transcript_keyword_cause and int_meeting_cause.
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

-- Decision text universe: one tsvector per decision from headline +
-- decision_statement. Only decisions with a c1_event_id (the meeting roll-up key)
-- are kept; in event_decision every row already has one.
decision_doc as (
    select
        d.event_decision_id,
        d.c1_event_id,
        to_tsvector(
            'english',
            lower(coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, ''))
        ) as content_tsv
    from {{ ref('event_decision') }} d
    where d.c1_event_id is not null
      and (
            nullif(trim(coalesce(d.headline, '')), '') is not null
         or nullif(trim(coalesce(d.decision_statement, '')), '') is not null
      )
),

phrase_hit as (
    select
        dd.event_decision_id,
        dd.c1_event_id,
        vq.cause_id,
        vq.keyword
    from decision_doc dd
    join valid_query vq
        on dd.content_tsv @@ vq.pq::tsquery
),

scored as (
    select
        event_decision_id,
        c1_event_id,
        cause_id,
        count(distinct keyword) as n_keyword_hits
    from phrase_hit
    group by event_decision_id, c1_event_id, cause_id
)

select distinct
    s.event_decision_id::text   as event_decision_id,
    s.c1_event_id::text         as c1_event_id,
    s.cause_id::text            as cause_id,
    cm.cause_name::text         as cause_name,
    cm.icon::text               as icon,
    cm.popularity_rank          as popularity_rank,
    s.n_keyword_hits::integer   as n_keyword_hits
from scored s
join cause_meta cm
    on cm.cause_id = s.cause_id
where s.n_keyword_hits >= 2
