{{ config(
    materialized='table',
    tags=['intermediate', 'trending_terms'],
    indexes=[{'columns': ['term_key'], 'unique': true}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '30min'"]
) }}

/*
    Hot words (#1399): one row per candidate term that passes the national volume floor, with how over-represented it
    is in heated public comment.

    Unit: a speaker in a meeting (meeting_speaker_position), with all of that speaker's public-comment segments in
    the meeting as one document (never a possible minor; counted meetings only, so no school board). Counting
    speakers, not words, keeps one long speech from carrying a term.

    Heated speaker = either
      * heat >= var trending_hot_min_heat (4) on meeting_speaker_position: today the AI meeting analysis's own rating;
        the classifier's rating lands in the same column (heat_method) once its paid run is approved, and is then used
        with no change here; or
      * the speaker spoke at a meeting where both sides spoke (public_lean = 'mixed') or officials went against the
        public (officials_sided_against_public) on any topic: topic_meeting_lean or data_center_meeting_lean.

    Score: the log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi and Quinn 2008), heated speakers
    against all other speakers, prior = the term's share of all speakers times var trending_hot_prior (500). hot_score is
    the z-score; it is null unless the term was said by at least var trending_hot_min_speakers heated speakers in at
    least var trending_hot_min_meetings meetings.
*/

{%- set min_heat = var('trending_hot_min_heat', 4) %}
{%- set a0 = var('trending_hot_prior', 500) %}
{%- set min_spk = var('trending_hot_min_speakers', 5) %}
{%- set min_mtg = var('trending_hot_min_meetings', 3) %}
{%- set min_b = var('trending_min_meetings_b', 15) %}

with contentious as (
    select video_id from {{ ref('topic_meeting_lean') }}
    where public_lean = 'mixed' or officials_sided_against_public
    union
    select video_id from {{ ref('data_center_meeting_lean') }}
    where public_lean = 'mixed' or officials_sided_against_public
),

speaker as materialized (
    select
        t.meeting_speaker_id,
        t.video_id,
        bool_or(coalesce(p.heat, 0) >= {{ min_heat }} or c.video_id is not null) as is_hot,
        to_tsvector('english', string_agg(f.comment_text, ' ' order by f.comment_index)) as tsv
    from {{ ref('int_meeting_comment__turns') }} as t
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = t.comment_segment_id
    inner join {{ ref('int_trending_term__meeting') }} as m on m.video_id = t.video_id and m.counted
    inner join {{ ref('meeting_speaker_position') }} as p on p.meeting_speaker_id = t.meeting_speaker_id
    left join contentious as c on c.video_id = t.video_id
    where f.is_public_comment and not f.possible_minor
    group by t.meeting_speaker_id, t.video_id
),

-- Terms with enough national volume this year to be shown at all.
term as (
    select c.term_key, c.term_tsquery::tsquery as q
    from {{ ref('int_trending_term__candidate') }} as c
    where c.drop_reason is null
      and c.term_key in (
          select term_key from {{ ref('int_trending_term__jurisdiction_year') }}
          where meeting_year = {{ var('trending_year_b', 2026) }}
          group by term_key having sum(meetings) >= {{ min_b }}
      )
),

hits as (
    select
        t.term_key,
        count(*) filter (where s.is_hot)                      as y_hot,
        count(*) filter (where not s.is_hot)                  as y_rest,
        count(distinct s.video_id) filter (where s.is_hot)    as hot_meetings
    from speaker as s
    inner join term as t on s.tsv @@ t.q
    group by t.term_key
),

totals as (
    select sum(y_hot)::numeric as n_hot, sum(y_rest)::numeric as n_rest, sum(y_hot + y_rest)::numeric as n_all
    from hits
),

scored as (
    select
        h.*,
        {{ a0 }} * (h.y_hot + h.y_rest) / nullif(tt.n_all, 0) as alpha,
        tt.n_hot, tt.n_rest
    from hits as h
    cross join totals as tt
)

select
    s.term_key::text                                   as term_key,
    s.y_hot::int                                       as hot_speakers,
    s.y_rest::int                                      as other_speakers,
    s.hot_meetings::int                                as hot_meetings,
    (case when s.y_hot >= {{ min_spk }} and s.hot_meetings >= {{ min_mtg }} and s.n_hot > 0 and s.n_rest > 0 then
        (
            ln((s.y_hot + s.alpha) / (s.n_hot + {{ a0 }} - s.y_hot - s.alpha))
            - ln((s.y_rest + s.alpha) / (s.n_rest + {{ a0 }} - s.y_rest - s.alpha))
        ) / sqrt(1.0 / (s.y_hot + s.alpha) + 1.0 / (s.y_rest + s.alpha))
     end)::numeric(10, 3)                              as hot_score
from scored as s
