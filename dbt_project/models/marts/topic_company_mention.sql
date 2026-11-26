{{ config(materialized='table', tags=['marts', 'topics', 'serving']) }}

/*
    Where a topic's companies are named (#1052). Grain: one row per (topic company, meeting video) and one row per
    (topic company, decision). Every row carries a verbatim excerpt of the record with the matched words in <mark>
    (the match-evidence rule); a row whose excerpt has no <mark> is dropped.

      short-term-rentals   short_term_rental_company_mention (#1015), as is.
      data-centers         meetings: the company named (whole word, case-insensitive) within ~250 characters of a data
                           center phrase, inside a data-center passage
                           (int_data_center_transcript__passage, the passages data_center_meeting_mention quotes), so a
                           passing "Google" elsewhere in a meeting doesn't count; first such passage per meeting.
                           decisions: decision_company_mention (#508), matched by operator name.
      seeded topics        meetings: only in a meeting already tagged with the topic (topic_transcript_link), and only
                           where the company is named (whole word, case-insensitive) within ~250 characters of one of
                           the topic's own keywords (curated_topics.keywords), in either order (#1155). A name used as
                           a landmark ("right next to The Picklr") or in an unrelated aside doesn't count; the quote is
                           that same passage. decisions: the company's match phrases in the decision's headline and
                           statement (event_decision.search_tsv), English full text, only in a decision tagged with
                           the topic (int_decision_topic): Motorola's radio contracts or Axon's body cameras don't count
                           toward license-plate readers unless that decision is about plate readers.
*/

with companies as (
    select
        c.*,
        '\m(' || array_to_string(array(
            select regexp_replace(t, '([.^$*+?()\[\]{}|\\])', '\\\1', 'g') from unnest(c.match_terms) as t
        ), '|') || ')\M'                                                            as term_regex,
        (select string_agg('(' || phraseto_tsquery('english', t)::text || ')', ' | ')
         from unnest(c.match_terms) as t
         where phraseto_tsquery('english', t)::text <> '')::tsquery                 as q_english,
        (select string_agg('(' || phraseto_tsquery('simple', t)::text || ')', ' | ')
         from unnest(c.match_terms) as t
         where phraseto_tsquery('simple', t)::text <> '')::tsquery                  as q_simple
    from {{ ref('topic_company') }} as c
),

-- The topic's own keywords as one whole-word alternation (#1155), for the seeded topics' proximity rule.
topic_terms as (
    select
        t.query_id::text                                                            as topic_query_id,
        '\m(' || array_to_string(array(
            select regexp_replace(lower(btrim(k)), '([.^$*+?()\[\]{}|\\])', '\\\1', 'g')
            from unnest(string_to_array(t.keywords, '|')) as k
            where btrim(k) <> ''
        ), '|') || ')\M'                                                            as topic_regex
    from {{ ref('curated_topics') }} as t
    where coalesce(btrim(t.keywords), '') <> ''
),

headline_opts as (
    select 'MaxFragments=2, MinWords=8, MaxWords=30, StartSel=<mark>, StopSel=</mark>'::text as o
),

str_rows as (
    select
        c.topic_company_id, m.mention_kind, m.video_id, m.event_decision_id, m.title, m.event_date,
        m.jurisdiction_name, m.state_code, m.state, m.url, m.evidence
    from {{ ref('short_term_rental_company_mention') }} as m
    inner join companies as c on c.topic_query_id = 'short-term-rentals' and c.company_key = m.company_key
),

dc_meeting_rows as (
    select distinct on (c.topic_company_id, mm.video_id)
        c.topic_company_id,
        'meeting'::text                                                             as mention_kind,
        mm.video_id,
        null::text                                                                  as event_decision_id,
        mm.meeting_title                                                            as title,
        mm.meeting_date                                                             as event_date,
        mm.jurisdiction_name,
        mm.state_code,
        mm.state,
        (case when mm.video_url like '%youtu%' and mm.start_seconds is not null
              then mm.video_url || (case when mm.video_url like '%?%' then '&' else '?' end)
                   || 't=' || floor(mm.start_seconds)::int || 's'
              else mm.video_url end)::text                                         as url,
        ts_headline('simple', p.passage_text, c.q_simple, (select o from headline_opts))::text as evidence
    from companies as c
    inner join {{ ref('int_data_center_transcript__passage') }} as p
        -- Named within ~250 characters of a data center phrase (PostgreSQL caps a regex repeat at 255), so a software
        -- license or a passing "Google" elsewhere in the same 3-minute passage doesn't count.
        on lower(p.passage_text) ~ c.term_regex
       and (
            lower(p.passage_text) ~ ('(data ?cent(er|re)s?|hyperscale|server farm).{0,250}' || c.term_regex)
            or lower(p.passage_text) ~ (c.term_regex || '.{0,250}(data ?cent(er|re)s?|hyperscale|server farm)')
       )
    inner join {{ ref('data_center_meeting_mention') }} as mm
        on mm.video_id = p.video_id and mm.passage_index = p.passage_index
    where c.topic_query_id = 'data-centers'
    order by c.topic_company_id, mm.video_id, mm.passage_index
),

dc_decision_rows as (
    select distinct on (c.topic_company_id, e.event_decision_id)
        c.topic_company_id,
        'decision'::text                                                            as mention_kind,
        m.video_id::text                                                            as video_id,
        e.event_decision_id::text                                                   as event_decision_id,
        e.headline::text                                                            as title,
        case when m.meeting_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' then left(m.meeting_date, 10)::date end as event_date,
        e.jurisdiction_name::text                                                   as jurisdiction_name,
        e.state_code::text                                                          as state_code,
        e.state::text                                                               as state,
        ('/decisions/' || e.event_decision_id)::text                                as url,
        d.evidence::text                                                            as evidence
    from {{ ref('decision_company_mention') }} as d
    inner join companies as c
        on c.topic_query_id = 'data-centers' and lower(c.company_name) = lower(d.operator_name)
    inner join {{ ref('event_decision') }} as e on e.event_decision_id::text = d.event_decision_id::text
    left join lateral (
        select em.video_id, em.meeting_date
        from {{ ref('event_meeting') }} as em
        where em.c1_event_id = e.c1_event_id
        order by em.event_meeting_id
        limit 1
    ) as m on true
    order by c.topic_company_id, e.event_decision_id
),

seed_meeting_rows as (
    select distinct on (c.topic_company_id, d.video_id)
        c.topic_company_id,
        'meeting'::text                                                             as mention_kind,
        d.video_id::text                                                            as video_id,
        null::text                                                                  as event_decision_id,
        d.event_title::text                                                         as title,
        d.event_date::date                                                          as event_date,
        d.jurisdiction_name::text                                                   as jurisdiction_name,
        d.state_code::text                                                          as state_code,
        d.state::text                                                               as state,
        coalesce(d.video_url, 'https://www.youtube.com/watch?v=' || d.video_id)::text as url,
        -- quoted from that passage plus ~150 characters either side, so the excerpt reads as a sentence
        ts_headline(
            'english',
            substr(d.content, greatest(1, strpos(d.content, p.passage) - 150), length(p.passage) + 300),
            c.q_english, (select o from headline_opts)
        )::text                                                                     as evidence
    from companies as c
    inner join topic_terms as tt
        on tt.topic_query_id = c.topic_query_id
    inner join {{ ref('topic_transcript_link') }} as tl
        on tl.topic_id::text = c.topic_id::text
    inner join {{ ref('event_documents') }} as d
        -- full text narrows to transcripts that name the company before the slower regex below
        on d.video_id = tl.video_id and d.content_tsv @@ c.q_english
    -- The company named within ~250 characters of a topic keyword, either order (PostgreSQL caps a regex repeat at
    -- 255). substring returns the outer group: the stretch from one to the other, in the transcript's own casing.
    -- A company whose own phrase carries a topic keyword ("flock safety" is a plate-reader keyword, "pickleball
    -- kingdom" holds "pickleball") needs only its name, as the topic tagger already counts that phrase.
    cross join lateral (
        select substring(
            d.content from
            case
                when exists (select 1 from unnest(c.match_terms) as m where m ~ tt.topic_regex)
                    then '(?i)(' || c.term_regex || ')'
                else '(?i)(' || tt.topic_regex || '.{0,250}' || c.term_regex
                     || '|' || c.term_regex || '.{0,250}' || tt.topic_regex || ')'
            end
        ) as passage
    ) as p
    where c.topic_query_id not in ('data-centers', 'short-term-rentals')
      and d.video_id is not null
      and p.passage is not null
    order by c.topic_company_id, d.video_id, d.event_document_id
),

seed_decision_rows as (
    select
        c.topic_company_id,
        'decision'::text                                                            as mention_kind,
        m.video_id::text                                                            as video_id,
        e.event_decision_id::text                                                   as event_decision_id,
        e.headline::text                                                            as title,
        case when m.meeting_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' then left(m.meeting_date, 10)::date end as event_date,
        e.jurisdiction_name::text                                                   as jurisdiction_name,
        e.state_code::text                                                          as state_code,
        e.state::text                                                               as state,
        ('/decisions/' || e.event_decision_id)::text                                as url,
        ts_headline(
            'english', coalesce(e.headline, '') || '. ' || coalesce(e.decision_statement, ''), c.q_english,
            (select o from headline_opts)
        )::text                                                                     as evidence
    from companies as c
    inner join {{ ref('int_decision_topic') }} as dt
        on dt.topic_id::text = c.topic_id::text
    inner join {{ ref('event_decision') }} as e
        on e.event_decision_id::text = dt.event_decision_id::text and e.search_tsv @@ c.q_english
    left join lateral (
        select em.video_id, em.meeting_date
        from {{ ref('event_meeting') }} as em
        where em.c1_event_id = e.c1_event_id
        order by em.event_meeting_id
        limit 1
    ) as m on true
    where c.topic_query_id not in ('data-centers', 'short-term-rentals')
),

unioned as (
    select * from str_rows
    union all select * from dc_meeting_rows
    union all select * from dc_decision_rows
    union all select * from seed_meeting_rows
    union all select * from seed_decision_rows
)

select distinct on (topic_company_id, mention_kind, coalesce(event_decision_id, video_id))
    md5(topic_company_id || '|' || mention_kind || '|' || coalesce(event_decision_id, video_id))::text
                                                                                    as topic_company_mention_id,
    topic_company_id,
    mention_kind,
    video_id,
    event_decision_id,
    title,
    event_date,
    jurisdiction_name,
    state_code,
    state,
    url,
    evidence
from unioned
where evidence like '%<mark>%'
  and coalesce(event_decision_id, video_id) is not null
order by topic_company_id, mention_kind, coalesce(event_decision_id, video_id), event_date desc nulls last
