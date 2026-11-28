{{ config(
    materialized='table',
    tags=['marts', 'serving', 'trending_terms'],
    contract={'enforced': true},
    indexes=[{'columns': ['scope_code', 'is_served']}, {'columns': ['term_key']}]
) }}

/*
    Trending terms in meeting speech (#1399). GRAIN: one row per (scope_code, term_key): the national scope ('US') and
    each state, for every kept candidate term (int_trending_term__candidate) said in that scope in either year.

    meetings_a / meetings_b  counted meetings (int_trending_term__meeting: recorded, not school board, transcript text)
                             in the scope whose transcript says the term, in year_a (last full year) and year_b (this
                             year to date).
    recorded_a / recorded_b  all counted meetings in the scope that year: the denominator, as /api/topics/yoy divides by
                             recorded_meeting_year (school boards left out of both sides here).
    share_*                  meetings / recorded (0-1); null when the scope recorded nothing that year.
    rise                     share_b / share_a; null when share_a is 0 (a term new this year).
    rise_score               ln of the ratio of smoothed shares ((meetings + 2) / recorded), so new and rare terms rank
                             sensibly. Ranking key for "rising".
    n_jurisdictions          distinct governments that said it in year_b.
    hot_score                national log-odds z-score from int_trending_term__hot (heat is too sparse per state, so a
                             state's "most heated" list ranks its own eligible terms by the national score).
    eligible                 meetings_b >= var trending_min_meetings_b (national 15, state var trending_state_min_meetings_b 5)
                             and n_jurisdictions >= var trending_min_jurisdictions (national 5, state 3), no one
                             government holds more than var trending_max_jurisdiction_share (40%) of year_b's meetings
                             (so one place, or one long meeting series, can't carry a term), and the scope recorded at
                             least 20 meetings in each year. Only eligible rows get ranks.
    rank_rising / rank_hot / rank_volume  1 = top, within the scope, over eligible rows that aren't a fragment of a
                             longer eligible term said in at least var trending_fragment_share (85%) as many meetings;
                             rising needs rise_score > 0, hot needs hot_score >= 1.96.
    is_served                within the top var trending_served_per_sort (100) of any of the three ranks: what
                             public.trending_term publishes.
*/

{%- set ya = var('trending_year_a', 2025) %}
{%- set yb = var('trending_year_b', 2026) %}
{%- set nat_b = var('trending_min_meetings_b', 15) %}
{%- set nat_j = var('trending_min_jurisdictions', 5) %}
{%- set st_b = var('trending_state_min_meetings_b', 5) %}
{%- set st_j = var('trending_state_min_jurisdictions', 3) %}
{%- set per_sort = var('trending_served_per_sort', 100) %}
{%- set max_jur = var('trending_max_jurisdiction_share', 0.4) %}

with jy as (
    select j.*
    from {{ ref('int_trending_term__jurisdiction_year') }} as j
    inner join {{ ref('int_trending_term__candidate') }} as c on c.term_key = j.term_key and c.drop_reason is null
),

scoped as (
    select 'US'::text as scope_code, term_key, jurisdiction_key, meeting_year, meetings, latest_meeting_date from jy
    union all
    select state_code, term_key, jurisdiction_key, meeting_year, meetings, latest_meeting_date from jy
    where state_code is not null
),

counts as (
    select
        scope_code, term_key,
        coalesce(sum(meetings) filter (where meeting_year = {{ ya }}), 0)               as meetings_a,
        coalesce(sum(meetings) filter (where meeting_year = {{ yb }}), 0)               as meetings_b,
        count(distinct jurisdiction_key) filter (where meeting_year = {{ yb }})         as n_jurisdictions,
        coalesce(max(meetings) filter (where meeting_year = {{ yb }}), 0)               as top_jurisdiction_b,
        max(latest_meeting_date)                                                        as latest_meeting_date
    from scoped
    group by scope_code, term_key
),

recorded as (
    select 'US'::text as scope_code,
           count(*) filter (where meeting_year = {{ ya }}) as recorded_a,
           count(*) filter (where meeting_year = {{ yb }}) as recorded_b
    from {{ ref('int_trending_term__meeting') }} where counted
    union all
    select state_code,
           count(*) filter (where meeting_year = {{ ya }}),
           count(*) filter (where meeting_year = {{ yb }})
    from {{ ref('int_trending_term__meeting') }} where counted and state_code is not null
    group by state_code
),

states as (
    select state_code, max(state) as state from {{ ref('int_trending_term__meeting') }}
    where state_code is not null
    group by state_code
),

base as (
    select
        c.*, r.recorded_a, r.recorded_b,
        case when r.recorded_a > 0 then c.meetings_a::numeric / r.recorded_a end as share_a,
        case when r.recorded_b > 0 then c.meetings_b::numeric / r.recorded_b end as share_b,
        case when r.recorded_a > 0 and r.recorded_b > 0 then
            ln(((c.meetings_b + 2.0) / r.recorded_b) / ((c.meetings_a + 2.0) / r.recorded_a)) end as rise_score,
        h.hot_score, coalesce(h.hot_speakers, 0) as hot_speakers,
        (case when c.scope_code = 'US'
              then c.meetings_b >= {{ nat_b }} and c.n_jurisdictions >= {{ nat_j }}
              else c.meetings_b >= {{ st_b }} and c.n_jurisdictions >= {{ st_j }} end
         and c.top_jurisdiction_b <= {{ max_jur }} * c.meetings_b
         and r.recorded_a >= 20 and r.recorded_b >= 20) as eligible
    from counts as c
    inner join recorded as r on r.scope_code = c.scope_code
    left join {{ ref('int_trending_term__hot') }} as h on h.term_key = c.term_key
),

-- A fragment of a longer eligible term that is said in nearly the same meetings ("term rental" inside "short term
-- rental", "automated license" inside "automated license plate") isn't ranked: the longer phrase stands for it.
fragment as (
    select distinct t.scope_code, t.term_key
    from base as u
    inner join {{ ref('int_trending_term__candidate') }} as uc on uc.term_key = u.term_key and uc.n_words >= 2
    cross join lateral (
        select array_to_string((string_to_array(uc.term, ' '))[a:b], ' ') as sub
        from generate_series(1, uc.n_words) as a, generate_series(1, uc.n_words) as b
        where b >= a and (b - a + 1) < uc.n_words
    ) as sp
    inner join {{ ref('int_trending_term__candidate') }} as tc on tc.term = sp.sub and tc.drop_reason is null
    inner join base as t on t.term_key = tc.term_key and t.scope_code = u.scope_code and t.eligible
    where u.eligible and u.meetings_b >= {{ var('trending_fragment_share', 0.85) }} * t.meetings_b
),

ranked as (
    select
        b.*,
        case when b.rankable and b.rise_score > 0 then
            row_number() over (partition by b.scope_code, (b.rankable and b.rise_score > 0)
                               order by b.rise_score desc, b.meetings_b desc, b.term_key) end as rank_rising,
        case when b.rankable and b.hot_score >= 1.96 then
            row_number() over (partition by b.scope_code, (b.rankable and b.hot_score >= 1.96)
                               order by b.hot_score desc, b.meetings_b desc, b.term_key) end as rank_hot,
        case when b.rankable then
            row_number() over (partition by b.scope_code, b.rankable
                               order by b.meetings_b desc, b.term_key) end as rank_volume
    from (
        select b0.*, (b0.eligible and f.term_key is null) as rankable
        from base as b0
        left join fragment as f on f.scope_code = b0.scope_code and f.term_key = b0.term_key
    ) as b
)

select
    md5(r.scope_code || '|' || r.term_key)::text                                  as trending_term_id,
    r.scope_code::text                                                            as scope_code,
    (case when r.scope_code <> 'US' then r.scope_code end)::text                  as state_code,
    st.state::text                                                                as state,
    r.term_key::text                                                              as term_key,
    c.term::text                                                                  as term,
    c.term_tsquery::text                                                          as term_tsquery,
    c.n_words::int                                                                as n_words,
    {{ ya }}::int                                                                 as year_a,
    {{ yb }}::int                                                                 as year_b,
    r.meetings_a::int                                                             as meetings_a,
    r.meetings_b::int                                                             as meetings_b,
    r.recorded_a::int                                                             as recorded_a,
    r.recorded_b::int                                                             as recorded_b,
    round(r.share_a, 6)::numeric(9, 6)                                            as share_a,
    round(r.share_b, 6)::numeric(9, 6)                                            as share_b,
    (case when r.share_a > 0 then round(r.share_b / r.share_a, 3) end)::numeric(12, 3) as rise,
    round(r.rise_score, 4)::numeric(10, 4)                                        as rise_score,
    (r.meetings_a + r.meetings_b)::int                                            as n_meetings,
    r.n_jurisdictions::int                                                        as n_jurisdictions,
    r.latest_meeting_date::date                                                   as latest_meeting_date,
    r.hot_score::numeric(10, 3)                                                   as hot_score,
    r.hot_speakers::int                                                           as hot_speakers,
    c.is_sensitive::boolean                                                       as is_sensitive,
    c.sensitive_category::text                                                    as sensitive_category,
    c.name_allowed_as::text                                                       as name_allowed_as,
    r.eligible::boolean                                                           as eligible,
    r.rank_rising::int                                                            as rank_rising,
    r.rank_hot::int                                                               as rank_hot,
    r.rank_volume::int                                                            as rank_volume,
    (coalesce(r.rank_rising, 1e9) <= {{ per_sort }} or coalesce(r.rank_hot, 1e9) <= {{ per_sort }}
     or coalesce(r.rank_volume, 1e9) <= {{ per_sort }})::boolean                  as is_served
from ranked as r
inner join {{ ref('int_trending_term__candidate') }} as c on c.term_key = r.term_key and c.drop_reason is null
left join states as st on st.state_code = r.scope_code
